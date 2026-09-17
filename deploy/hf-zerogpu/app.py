"""VERA API + worker launcher for a free Hugging Face Gradio Space on ZeroGPU hardware.

Why this shape: Docker Spaces and CPU-basic Gradio Spaces require a PRO plan, while a Gradio
Space on ZeroGPU hardware is free. ZeroGPU stops any app that never reports startup, and that
report is normally sent by ``gradio.Blocks.launch``. This launcher instead serves the existing
FastAPI app with uvicorn and sends the report itself (``spaces.zero.startup``). All inference
runs on CPU with onnxruntime; the GPU is never requested, so the ZeroGPU quota is not used.

One container owns: loopback Redis (Celery broker), Alembic migrations, one solo Celery worker
(which downloads the models from ``HF_MODEL_REPO`` and runs the outbox dispatcher), and the API
on port 7860. If Redis or the worker exits, the process exits so the Space restarts.

Required Space secrets: DATABASE_URL, HF_MODEL_REPO, HF_TOKEN (read), SECRET_KEY, CORS_ORIGINS.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import spaces  # must be imported before any CUDA-related package

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
MODEL_DIR = Path(os.environ.get("MODEL_DIR", "/home/user/models"))
REDIS_URL = "redis://127.0.0.1:6379/0"

for name in ("DATABASE_URL", "HF_MODEL_REPO"):
    if not os.environ.get(name):
        sys.exit(f"Set {name} in the Space secrets")

os.environ.update(
    ENVIRONMENT="production",
    MODEL_DIR=str(MODEL_DIR),
    REDIS_URL=REDIS_URL,
    CELERY_BROKER_URL=REDIS_URL,
    CELERY_RESULT_BACKEND="",
)
MODEL_DIR.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)


@spaces.GPU
def _zerogpu_placeholder() -> str:
    """ZeroGPU only reports startup when at least one GPU function exists. Never called."""
    return "unused"


def _log(message: str) -> None:
    print(f"[vera-launcher] {message}", flush=True)


def start_redis() -> subprocess.Popen[bytes]:
    Path("/tmp/redis").mkdir(exist_ok=True)
    proc = subprocess.Popen(
        [
            "redis-server",
            "--bind",
            "127.0.0.1",
            "--protected-mode",
            "yes",
            "--port",
            "6379",
            "--dir",
            "/tmp/redis",
            "--save",
            "",
            "--appendonly",
            "no",
        ]
    )
    for _ in range(30):
        ping = subprocess.run(["redis-cli", "-h", "127.0.0.1", "ping"], capture_output=True)
        if ping.stdout.strip() == b"PONG":
            _log("redis ready")
            return proc
        if proc.poll() is not None:
            break
        time.sleep(1)
    sys.exit("redis-server failed to start")


def run_migrations() -> None:
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    _log("database migrations applied")


def start_worker() -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "celery",
            "-A",
            "app.worker.celery_app",
            "worker",
            "--pool=solo",
            "--concurrency=1",
            "--loglevel=info",
        ]
    )


def supervise(children: dict[str, subprocess.Popen[bytes]]) -> None:
    """Exit the whole Space if a required child dies, so the platform restarts it."""
    while True:
        for name, proc in children.items():
            if proc.poll() is not None:
                _log(f"{name} exited with code {proc.returncode}; stopping the Space")
                for other in children.values():
                    if other.poll() is None:
                        other.terminate()
                os._exit(1)
        time.sleep(5)


def main() -> None:
    import uvicorn

    redis_proc = start_redis()
    run_migrations()
    worker = start_worker()
    threading.Thread(
        target=supervise, args=({"redis": redis_proc, "worker": worker},), daemon=True
    ).start()

    from app.main import app

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {"service": "VERA review analysis API", "health": "/health", "ready": "/ready"}

    zero = getattr(spaces, "zero", None)
    if zero is not None and hasattr(zero, "startup"):
        zero.startup()
        _log("ZeroGPU startup reported")
    uvicorn.run(app, host="0.0.0.0", port=7860, proxy_headers=False, access_log=False)


if __name__ == "__main__":
    main()
