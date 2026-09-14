"""Model artifact registry and HuggingFace Hub download (PRD §17.3).

Production policy (user decision, see DECISIONS.md): the worker **hard-fails**
if any artifact is missing. There is no heuristic fallback.

CLI (from ``backend/``)::

    python -m app.ml.models.loader          # download missing artifacts, then verify
    python -m app.ml.models.loader --check  # verify only, no network
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Final

logger = logging.getLogger(__name__)

#: Every file the production pipeline needs, with the notebook that produces it.
REQUIRED_ARTIFACTS: Final[dict[str, str]] = {
    "experience_model.onnx": "notebooks/04_finetune_experience.ipynb (INT8 ONNX)",
    "experience_tokenizer.json": "notebooks/04_finetune_experience.ipynb",
    "absa_model.onnx": "notebooks/04_finetune_experience.ipynb (ABSA export section)",
    "absa_tokenizer.json": "notebooks/04_finetune_experience.ipynb (ABSA export section)",
    "absa_config.json": "notebooks/04_finetune_experience.ipynb (ABSA export section)",
    "domain_tfidf.joblib": "notebooks/05_train_fusion.ipynb (domain model section)",
    "fusion_ensemble.json": "notebooks/05_train_fusion.ipynb",
    "conformal_qhat.json": "notebooks/06_calibration.ipynb",
}


class ModelArtifactsMissingError(RuntimeError):
    """Raised when required model artifacts are absent after any download attempt."""

    def __init__(self, model_dir: Path, missing: list[str]) -> None:
        self.model_dir = model_dir
        self.missing = missing
        details = "\n".join(
            f"  - {name}  <- produced by {REQUIRED_ARTIFACTS[name]}" for name in missing
        )
        super().__init__(
            f"{len(missing)} required model artifact(s) missing in {model_dir}:\n{details}\n"
            "Run notebooks 04 (Colab) and 05-06 (local), then upload the files to "
            "HF_MODEL_REPO or copy them into MODEL_DIR."
        )


def missing_artifacts(model_dir: Path) -> list[str]:
    """Return the names of required artifacts not present (or empty) in ``model_dir``."""
    return [
        name
        for name in REQUIRED_ARTIFACTS
        if not (model_dir / name).is_file() or (model_dir / name).stat().st_size == 0
    ]


def artifact_status(model_dir: Path) -> dict[str, bool]:
    """Map each required artifact to whether it is present. Used by ``/health``."""
    missing = set(missing_artifacts(model_dir))
    return {name: name not in missing for name in REQUIRED_ARTIFACTS}


def ensure_models(model_dir: Path, hf_repo: str = "", hf_token: str = "") -> dict[str, Path]:
    """Download missing artifacts from the Hub (if configured) and verify all exist.

    Args:
        model_dir: Local artifact directory (created if absent).
        hf_repo: ``user/repo`` on HuggingFace Hub; empty disables downloading.
        hf_token: Optional token for private repos.

    Returns:
        Mapping of artifact name to its local path.

    Raises:
        ModelArtifactsMissingError: If anything is still missing afterwards.
    """
    model_dir.mkdir(parents=True, exist_ok=True)
    missing = missing_artifacts(model_dir)

    if missing and hf_repo:
        from huggingface_hub import hf_hub_download  # imported lazily: network-only path

        for name in missing:
            logger.info("Downloading %s from %s ...", name, hf_repo)
            try:
                hf_hub_download(
                    repo_id=hf_repo,
                    filename=name,
                    local_dir=model_dir,
                    token=hf_token or None,
                )
            except Exception as exc:  # report every failure, then fail once below
                logger.error("Failed to download %s: %s", name, exc)
        missing = missing_artifacts(model_dir)

    if missing:
        raise ModelArtifactsMissingError(model_dir, missing)

    logger.info("All %d model artifacts ready in %s", len(REQUIRED_ARTIFACTS), model_dir)
    return {name: model_dir / name for name in REQUIRED_ARTIFACTS}


def _main(argv: list[str] | None = None) -> int:
    from app.config import settings

    parser = argparse.ArgumentParser(description="Download / verify VERA model artifacts.")
    parser.add_argument("--check", action="store_true", help="verify only; never download")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    try:
        ensure_models(
            settings.MODEL_DIR,
            hf_repo="" if args.check else settings.HF_MODEL_REPO,
            hf_token=settings.HF_TOKEN,
        )
    except ModelArtifactsMissingError as exc:
        logger.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_main())
