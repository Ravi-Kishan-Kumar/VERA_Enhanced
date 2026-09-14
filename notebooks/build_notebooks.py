"""Generate notebooks 01–08 from this single, reviewable source.

    .venv\\Scripts\\python.exe notebooks\\build_notebooks.py

Notebooks are thin wrappers: all logic lives in the tested `training/vera_training`
package and the production `backend/app` package. Edit THIS file, not the .ipynb.

Where each notebook runs:
  01–03, 05–08  local VS Code Jupyter with the repo `.venv` (Python 3.12, production pins)
  04            Google Colab GPU (browser or VS Code Colab extension); the same training
                also runs locally via training/scripts/train_all.py for a comparable model
Running 05–08 locally guarantees the domain-model pickle and XGBoost artifacts are built
with exactly the library versions the Render worker uses.
"""

from __future__ import annotations

from pathlib import Path

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

HERE = Path(__file__).resolve().parent

SETUP = """\
# --- Repo setup: make `app` (backend) and `vera_training` importable ---------
import sys
from pathlib import Path

ROOT = Path.cwd().resolve()
while not (ROOT / "PRD.md").exists() and ROOT != ROOT.parent:
    ROOT = ROOT.parent
for sub in ("backend", "training"):
    if str(ROOT / sub) not in sys.path:
        sys.path.insert(0, str(ROOT / sub))

import os
if not (ROOT / ".env").exists():  # app settings require these; real values come from .env
    os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from vera_training import paths
paths.ensure_dirs()
print("Repo root:", ROOT)"""


def md(text: str) -> nbformat.NotebookNode:
    return new_markdown_cell(text.strip())


def code(text: str) -> nbformat.NotebookNode:
    return new_code_cell(text.strip())


NOTEBOOKS: dict[str, list[nbformat.NotebookNode]] = {}

# --------------------------------------------------------------------------- 01
NOTEBOOKS["01_data_exploration"] = [
    md("""
# 01 · Data exploration & corpus preparation (PRD §6)
**Runs:** locally (`.venv`). **Produces:** `data/processed/earbud_reviews.parquet`,
`data/processed/labeling_pool.parquet`.

1. Download the Electronics review + metadata files (~25 GB total, one time).
2. Filter to earbud products, clean text with the production Agent 1 cleaner,
   drop < 20-word and duplicate reviews.
3. Draw the star-stratified 2,000-review labeling pool (400 per star, ≤ 5 per product).
"""),
    code(SETUP),
    md("""
## 1. Download raw files
The files below are the raw JSONL exports in the dataset repo. Confirm the paths on
https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/tree/main/raw
before running. Skipped automatically if the files already exist.
"""),
    code("""
from huggingface_hub import hf_hub_download

FILES = {
    "meta_Electronics.jsonl": "raw/meta_categories/meta_Electronics.jsonl",
    "Electronics.jsonl": "raw/review_categories/Electronics.jsonl",
}
for local_name, repo_path in FILES.items():
    target = paths.RAW / local_name
    if target.exists():
        print("exists:", target)
        continue
    downloaded = hf_hub_download(
        "McAuley-Lab/Amazon-Reviews-2023", repo_path, repo_type="dataset", local_dir=paths.RAW
    )
    Path(downloaded).rename(target)
    print("downloaded:", target)
"""),
    md("## 2. Filter + clean (streams the 20+ GB review file; ~20–40 min)"),
    code("""
from vera_training.data import json_records, prepare_corpus

if paths.CORPUS.exists():
    import pandas as pd
    corpus = pd.read_parquet(paths.CORPUS)
else:
    corpus = prepare_corpus(
        json_records(paths.RAW / "Electronics.jsonl"),
        json_records(paths.RAW / "meta_Electronics.jsonl"),
        min_words=20,
    )
    corpus.to_parquet(paths.CORPUS, index=False)
print(f"{len(corpus):,} earbud reviews across {corpus.parent_asin.nunique():,} products")
"""),
    md("## 3. Exploration — how inflated are the stars?"),
    code("""
import matplotlib.pyplot as plt

share = corpus.rating.value_counts(normalize=True).sort_index()
print((share * 100).round(1).astype(str) + "%")
share.plot.bar(title="Star distribution (earbuds)", ylabel="share", xlabel="stars")
plt.show()

reviews_per_product = corpus.parent_asin.value_counts()
print(reviews_per_product.describe())
print("Products with exactly 1 review:", (reviews_per_product == 1).sum())
"""),
    md("## 4. Labeling pool (PRD §6.3)"),
    code("""
from vera_training.data import sample_for_labeling

pool = sample_for_labeling(corpus, n=2000, seed=42, product_cap=5)
pool.to_parquet(paths.LABELING_POOL, index=False)
print(pool.rating.value_counts().sort_index())
print("max reviews per product:", pool.parent_asin.value_counts().max())
"""),
]

# --------------------------------------------------------------------------- 02
NOTEBOOKS["02_label_generation"] = [
    md("""
# 02 · Label generation (PRD §7)
**Runs:** locally. **Needs:** `GEMINI_API_KEY` (and `GEMINI_MODEL`) in the repo `.env`.
**Produces:** `data/labels/run_primary.json` (resumable checkpoint).

The prompt is the PRD §7.2 prompt verbatim; the star rating is never sent. Re-running
this notebook resumes from the checkpoint — completed labels are never re-requested.
`MAX_REQUESTS` is a hard budget including retries.
"""),
    code(SETUP),
    code("""
from dotenv import load_dotenv
import pandas as pd
from vera_training.labeling import Provider, run_labels

load_dotenv(ROOT / ".env")
pool = pd.read_parquet(paths.LABELING_POOL)

MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
MAX_REQUESTS = 2600          # 2000 labels + retry headroom
REQUESTS_PER_MINUTE = 10     # stay well inside free-tier rate limits

provider = Provider("gemini", MODEL)
state = run_labels(
    pool, paths.PRIMARY_RUN, provider,
    provider_name="gemini", model=MODEL, run_id="primary", seed=1,
    max_requests=MAX_REQUESTS, requests_per_minute=REQUESTS_PER_MINUTE,
)
print(f"labels: {len(state['labels'])}/{len(pool)}  requests used: {state['requests']}")
print("rows with errors:", len(state["errors"]))
"""),
    md("## Label distribution (should be far less skewed than the stars)"),
    code("""
scores = pd.Series({k: v["experience_score"] for k, v in state["labels"].items()})
stars = pool.set_index("review_id").rating.reindex(scores.index)
print(scores.value_counts().sort_index())
print("mean |star - label|:", (stars - scores).abs().mean().round(3))
print("irony/sarcasm flagged:", sum(v["has_irony_or_sarcasm"] for v in state["labels"].values()))
"""),
]

# --------------------------------------------------------------------------- 03
NOTEBOOKS["03_agreement_analysis"] = [
    md("""
# 03 · Agreement analysis — gate G1 (PRD §7.4, §20.1)
**Runs:** locally. **Produces:** `data/labels/agreement_report.json`, `data/labels/labels_v1.jsonl`.

1. Independent second labeling run (different run id + seed) on 200 reviews → self-consistency.
2. Blinded reference sheet (text only — no stars, no model labels) → an annotator fills
   `experience_score`.
3. Gate: self κ > 0.70, reference κ > 0.55, self MAE < 0.40, reference MAE < 0.60.
   If it fails: add few-shot examples / chain-of-thought as PRD §7.4 suggests, then relabel
   with a NEW run id (the checkpoint refuses prompt changes by design).
"""),
    code(SETUP),
    code("""
from dotenv import load_dotenv
import pandas as pd
from vera_training.labeling import Provider, run_labels

load_dotenv(ROOT / ".env")
pool = pd.read_parquet(paths.LABELING_POOL)
subset = pool.sample(n=200, random_state=7)
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

state = run_labels(
    subset, paths.CONSISTENCY_RUN, Provider("gemini", MODEL),
    provider_name="gemini", model=MODEL, run_id="consistency", seed=2,
    max_requests=300, requests_per_minute=10,
)
print("second-run labels:", len(state["labels"]))
"""),
    md("## Optional human validation — use only annotations supplied by a person"),
    md("""
Fill the `experience_score` column (1.0 … 5.0 in 0.5 steps). LLM-generated reference
annotations must not be described as human validation.
"""),
    code("""
from vera_training.agreement import export_human_sheet

if not paths.HUMAN_SHEET.exists():
    export_human_sheet(subset, paths.HUMAN_SHEET, n=200, seed=42)
    print("Created", paths.HUMAN_SHEET, "- annotate it, then run the next cell.")
else:
    print("Sheet exists:", paths.HUMAN_SHEET)
"""),
    code("""
from vera_training.agreement import agreement_report

report = agreement_report(
    paths.PRIMARY_RUN, paths.CONSISTENCY_RUN, paths.HUMAN_SHEET, paths.AGREEMENT_REPORT,
    reference_annotator="human"
)
import json
print(json.dumps(
    {k: report[k] for k in ("passed", "human_validated", "self_consistency", "reference_agreement")},
    indent=2,
))
"""),
    md("## Freeze labels (only after G1 passes)"),
    code("""
import json
from vera_training.agreement import require_label_gate
from vera_training.labeling import merge_labels

require_label_gate(paths.AGREEMENT_REPORT)
labelled = merge_labels(pool, paths.PRIMARY_RUN)
with paths.LABELS_V1.open("w", encoding="utf-8") as stream:
    for record in labelled.to_dict(orient="records"):
        stream.write(json.dumps(record, default=str) + "\\n")
print(f"Wrote {len(labelled)} labels to {paths.LABELS_V1}")
"""),
]

# --------------------------------------------------------------------------- 04
NOTEBOOKS["04_finetune_experience"] = [
    md("""
# 04 · Fine-tune Agent 2 on Colab GPU (PRD §12, gate G2)
**Runs:** Google Colab with a **T4 GPU** — either in the browser or from VS Code with Google's
official *Colab* extension (open this notebook → *Select Kernel* → *Colab* → *New Colab Server* → GPU).

The same training also runs locally on a small GPU via `training/scripts/train_all.py`
(384 tokens, Adafactor). This notebook uses the full profile (512 tokens, AdamW) so the two
models can be compared on **identical product-grouped folds** (`GroupKFold` is deterministic).

**Inputs** (pick one in the next cell):
- `REPO_URL` — your GitHub repo **plus** `labels_v1.jsonl` uploaded next to this notebook, or
- `dist/vera_colab_bundle.zip` from `training/scripts/make_colab_bundle.py`, uploaded to
  `/content` (Files panel) or Drive `MyDrive/vera/`.

**Outputs** (zipped to `/content/vera_colab_outputs.zip` for download, copied to Drive if mounted):
`experience_oof_colab.csv` (out-of-fold predictions for the comparison), `final_model_colab/`
(PyTorch weights + tokenizer, ~750 MB) and `colab_run.json`. Save the zip to
`C:\\Workspace\\VERA\\colab_results\\`; Claude compares the models and, if Colab wins, exports it locally.
"""),
    code("""
# --- Environment ------------------------------------------------------------------
import os, sys, subprocess, zipfile, pathlib

REPO_URL = ""                      # e.g. "https://github.com/you/vera.git" (optional)
USE_DRIVE = False                  # True: read bundle from / write outputs to MyDrive/vera
ROOT = pathlib.Path("/content/vera")
DRIVE = pathlib.Path("/content/drive/MyDrive/vera")

if USE_DRIVE:
    from google.colab import drive
    drive.mount("/content/drive")

if not ROOT.exists():
    bundle = next((p for p in [pathlib.Path("/content/vera_colab_bundle.zip"),
                               DRIVE / "vera_colab_bundle.zip"] if p.exists()), None)
    if REPO_URL:
        subprocess.run(["git", "clone", "--depth", "1", REPO_URL, str(ROOT)], check=True)
    else:
        if bundle is None:
            # No bundle on the server yet: open a file picker (works in browser Colab and the
            # VS Code Colab extension). Choose C:\\Workspace\\VERA\\dist\\vera_colab_bundle.zip
            import shutil
            from google.colab import files
            print("Select vera_colab_bundle.zip (C:\\\\Workspace\\\\VERA\\\\dist\\\\) in the picker...")
            uploaded = files.upload()
            if not uploaded:
                raise FileNotFoundError("No file uploaded; re-run this cell and choose the zip")
            bundle = pathlib.Path("/content/vera_colab_bundle.zip")
            shutil.move(next(iter(uploaded)), bundle)
        zipfile.ZipFile(bundle).extractall(ROOT)

# Colab ships torch, transformers, scikit-learn, pandas and numpy for its own Python version
# (3.13 as of 2026-09); pinned production versions do not exist there. Only install what is
# missing, unpinned. The production-compatible ONNX export happens locally, not here.
subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                "datasets", "accelerate", "sentencepiece", "protobuf"], check=True)
os.chdir(ROOT)
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "training")]
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

import torch
assert torch.cuda.is_available(), "Switch the runtime to a GPU (T4)"
print("GPU:", torch.cuda.get_device_name(0))
"""),
    code("""
import json
import pandas as pd
from vera_training.io import validate_reviews

labels_path = next(p for p in [ROOT / "data/labels/labels_v1.jsonl",
                               pathlib.Path("/content/labels_v1.jsonl"),
                               DRIVE / "labels_v1.jsonl"] if p.exists())
rows = [json.loads(line) for line in labels_path.open(encoding="utf-8")]
labelled = validate_reviews(pd.DataFrame(rows), labels=True)
print(len(labelled), "labelled reviews,", labelled.parent_asin.nunique(), "products")
WORK = (DRIVE if USE_DRIVE else pathlib.Path("/content")) / "vera_work"
OUT = pathlib.Path("/content/vera_colab_outputs"); OUT.mkdir(exist_ok=True)
"""),
    md("## Cross-fitted out-of-fold predictions (5 product-grouped folds, resumable)"),
    code("""
from vera_training.finetune import FinetuneConfig, crossfit_predictions

config = FinetuneConfig()          # 512 tokens, AdamW, batch 8 (T4 profile)
oof = crossfit_predictions(labelled, WORK / "crossfit", config, n_folds=5)
out = pd.DataFrame({"review_id": labelled.review_id, "experience_raw": oof})
out.to_csv(OUT / "experience_oof_colab.csv", index=False)
print("OOF MAE:", float((out.experience_raw.clip(1, 5) - labelled.experience_score).abs().mean()))
"""),
    md("""
## Final model (PyTorch weights; ONNX export happens locally)
Exporting here would produce an ONNX graph from Colab's library versions. Instead the trained
weights are zipped; `train_all.py`'s export step converts them locally with the production-pinned
stack and runs the G2 parity check.
"""),
    code("""
import shutil
from vera_training.finetune import train_final

final_dir = WORK / "final" / "model"
if not (final_dir / "config.json").exists():
    final_dir = train_final(labelled, WORK / "final", config)
validation = json.loads((final_dir / "vera_training.json").read_text())["validation"]
print("final model validation:", validation)
shutil.copytree(final_dir, OUT / "final_model_colab", dirs_exist_ok=True)
(OUT / "colab_run.json").write_text(json.dumps({
    "config": {"max_length": config.max_length, "optim": config.optim, "epochs": config.epochs},
    "validation": validation,
    "torch": torch.__version__,
    "python": sys.version.split()[0],
}, indent=2))
"""),
    code("""
archive = shutil.make_archive("/content/vera_colab_outputs", "zip", OUT)
if USE_DRIVE:
    shutil.copy(archive, DRIVE / "vera_colab_outputs.zip")
print("Download:", archive)
try:
    from google.colab import files
    files.download(archive)
except Exception:
    print("Use the Colab Files panel to download it.")
"""),
]

# --------------------------------------------------------------------------- 05
NOTEBOOKS["05_train_fusion"] = [
    md("""
# 05 · Domain model (Agent 6) + fusion ensemble (Agent 7) (PRD §9, §10)
**Runs:** locally (`.venv`, production pins). **Needs:** notebooks 01, 03, 04 outputs.
**Produces:** `data/models/domain_tfidf.joblib`, `data/models/fusion_ensemble.json`,
`data/processed/fusion_cache.joblib` (feature matrices for 06–08).

Splits are product-grouped 60/20/20 (train / calibration / test). Training features use
50% metadata dropout; calibration and test features hide ALL metadata, exactly like API
submissions (PRD weakness #15).
"""),
    code(SETUP),
    code("""
import json
import pandas as pd
from vera_training.io import validate_reviews

corpus = pd.read_parquet(paths.CORPUS)
labelled = validate_reviews(
    pd.DataFrame([json.loads(l) for l in paths.LABELS_V1.open(encoding="utf-8")]), labels=True
)
oof = pd.read_csv(paths.EXPERIENCE_OOF, dtype={"review_id": str})
labelled = labelled.merge(oof, on="review_id", validate="one_to_one")
assert len(labelled) == len(oof), "OOF predictions must cover every label"
print(len(corpus), "corpus rows;", len(labelled), "labelled rows")
"""),
    md("## Agent 6 — leakage-guarded domain model (excludes ALL labelled products)"),
    code("""
from vera_training.domain import train_domain_model

report = train_domain_model(corpus, set(labelled.parent_asin), paths.MODELS / "domain_tfidf.joblib")
print(report)
"""),
    md("## Signal agents (production classes) and splits"),
    code("""
from app.ml.agents.absa import ABSAModule
from app.ml.agents.consistency import ConsistencyScorer
from app.ml.agents.domain_rating import DomainRatingModel
from app.ml.agents.preprocessor import TextPreprocessor
from app.ml.agents.quality import QualityAssessor
from app.ml.pipeline import SignalAgents
from vera_training import signals, splits

parts = splits.train_cal_test(labelled, seed=42)
means = signals.imputation_means(parts["train"])
agents = SignalAgents(
    preprocessor=TextPreprocessor(),
    experience=None,  # out-of-fold scores are supplied instead
    absa=ABSAModule(paths.MODELS / "absa_model.onnx", paths.MODELS / "absa_tokenizer.json",
                    paths.MODELS / "absa_config.json"),
    consistency=ConsistencyScorer(),
    quality=QualityAssessor(means),
    domain=DomainRatingModel(paths.MODELS / "domain_tfidf.joblib"),
)
print({k: len(v) for k, v in parts.items()}, "imputation means:", means)
"""),
    code("""
matrices = {}
for name, frame in parts.items():
    dropout = 0.5 if name == "train" else 1.0
    X, outputs = signals.feature_matrix(frame, agents, frame.experience_raw.to_numpy(),
                                        metadata_dropout=dropout, seed=42)
    matrices[name] = {"X": X, "y": frame.experience_score.to_numpy(), "frame": frame,
                      "aspects": [o["absa"]["aspects"] for o in outputs]}
# Full labelled set (for cross-validation in notebook 07)
X_all, _ = signals.feature_matrix(labelled, agents, labelled.experience_raw.to_numpy(),
                                  metadata_dropout=0.5, seed=7)
matrices["all"] = {"X": X_all, "y": labelled.experience_score.to_numpy(), "frame": labelled}
print({k: v["X"].shape for k, v in matrices.items()})
"""),
    md("## Agent 7 — 20-member bootstrap ensemble on the TRAIN split only"),
    code("""
import joblib
from vera_training.fusion import BootstrapEnsemble

ensemble = BootstrapEnsemble(n_members=20, seed=42).fit(matrices["train"]["X"], matrices["train"]["y"])
ensemble.save(paths.MODELS / "fusion_ensemble.json", means,
              metadata={"n_train": len(parts["train"]), "label_file": paths.LABELS_V1.name})
joblib.dump({"matrices": matrices, "imputation_means": means}, paths.FUSION_CACHE)

import numpy as np
for split in ("calibration", "test"):
    pred = ensemble.predict(matrices[split]["X"])
    print(split, "MAE:", np.abs(pred - matrices[split]["y"]).mean().round(3),
          "| stars-as-prediction MAE:",
          np.abs(matrices[split]["frame"].rating - matrices[split]["y"]).mean().round(3))
"""),
]

# --------------------------------------------------------------------------- 06
NOTEBOOKS["06_calibration"] = [
    md("""
# 06 · Split-conformal calibration (PRD §10.3)
**Runs:** locally. **Produces:** `data/models/conformal_qhat.json`.

Checklist enforced in code: calibration set product-disjoint from training; built with
API-like (fully imputed) metadata; coverage on the held-out TEST split ≥ nominal − 2%
before anything is written.
"""),
    code(SETUP),
    code("""
import joblib
import pandas as pd
from app.ml.agents.fusion import FusionModel
from vera_training import calibration
from vera_training.splits import assert_disjoint

cache = joblib.load(paths.FUSION_CACHE)["matrices"]
assert_disjoint(cache["train"]["frame"].parent_asin, cache["calibration"]["frame"].parent_asin,
                cache["test"]["frame"].parent_asin)
fusion = FusionModel(paths.MODELS / "fusion_ensemble.json")

def predict(split):
    members = fusion.predict_members(cache[split]["X"])
    return members.mean(axis=0).clip(1, 5), members.std(axis=0), cache[split]["y"]

cal, test = predict("calibration"), predict("test")
"""),
    code("""
rows = []
for alpha in (0.05, 0.10, 0.20):
    payload = calibration.fit_best_conformal(*cal, alpha=alpha)
    metrics = calibration.interval_metrics(*test, payload)
    rows.append({"target": 1 - alpha, "method": payload["method"], "q_hat": payload["q_hat"],
                 "test_coverage": metrics["coverage"], "test_mean_width": metrics["mean_width"],
                 "ok": metrics["coverage"] >= 1 - alpha - 0.02})
    if alpha == 0.10:
        production, production_test = payload, metrics
pd.DataFrame(rows)
"""),
    code("""
calibration.save_conformal(production, paths.MODELS / "conformal_qhat.json",
                           test_metrics=production_test)
print("Saved", paths.MODELS / "conformal_qhat.json", production)

# Optional: record in the CALIBRATION_CHECKPOINTS table (uses DATABASE_URL from .env;
# run `alembic upgrade head` against that database first).
# print("checkpoint id:", calibration.record_checkpoint(production))
"""),
    md("""
## Upload all artifacts to HuggingFace Hub
Requires `HF_TOKEN` and `HF_MODEL_REPO` in `.env`. Refuses to upload an incomplete set.
"""),
    code("""
from dotenv import load_dotenv
from vera_training.hub import upload_artifacts

load_dotenv(ROOT / ".env")
uploaded = upload_artifacts(paths.MODELS, os.environ["HF_MODEL_REPO"], os.environ["HF_TOKEN"])
print("uploaded:", uploaded)
"""),
]

# --------------------------------------------------------------------------- 07
NOTEBOOKS["07_ablation_study"] = [
    md("""
# 07 · Cross-validation & ablation (PRD §13.1–13.2)
**Runs:** locally (~10–30 min). **Produces:** `reports/cv_comparison.json`, `reports/ablation.csv`.

15 product-grouped folds (5 folds × 3 repeats). Baseline = Ridge on the star rating alone.
Components are kept only if they improve MAE in ≥ 60% of folds; negative results stay in the table.
"""),
    code(SETUP),
    code("""
import json
import joblib
from sklearn.linear_model import Ridge
from vera_training import evaluation
from vera_training.fusion import BootstrapEnsemble

data = joblib.load(paths.FUSION_CACHE)["matrices"]["all"]
X, y, groups = data["X"], data["y"], data["frame"].parent_asin.tolist()

baseline = evaluation.cross_validated_mae(X[:, :1], y, groups, Ridge)
vera = evaluation.cross_validated_mae(X, y, groups, lambda: BootstrapEnsemble(n_members=20))
comparison = evaluation.paired_comparison(baseline, vera)
(paths.REPORTS / "cv_comparison.json").write_text(json.dumps(comparison, indent=2))
print(json.dumps(comparison, indent=2))
"""),
    code("""
table = evaluation.ablation_study(X, y, groups, lambda: BootstrapEnsemble(n_members=5))
table.to_csv(paths.REPORTS / "ablation.csv", index=False)
table
"""),
]

# --------------------------------------------------------------------------- 08
NOTEBOOKS["08_evaluation_report"] = [
    md("""
# 08 · Evaluation report — gates G3 & G4, success criteria (PRD §13, §20.1, §22)
**Runs:** locally. **Needs:** notebooks 05–07. **Produces:** `reports/evaluation_report.json`.
"""),
    code(SETUP),
    code("""
import json, time
import joblib
import pandas as pd
from app.ml.calibration.conformal import ConformalPredictor
from app.ml.agents.fusion import FusionModel
from vera_training import calibration, evaluation
from vera_training.agreement import get_reference_agreement

cache = joblib.load(paths.FUSION_CACHE)["matrices"]
comparison = json.loads((paths.REPORTS / "cv_comparison.json").read_text())
fusion = FusionModel(paths.MODELS / "fusion_ensemble.json")
conformal = json.loads((paths.MODELS / "conformal_qhat.json").read_text())

members = fusion.predict_members(cache["test"]["X"])
coverage = calibration.interval_metrics(members.mean(0).clip(1, 5), members.std(0),
                                        cache["test"]["y"], conformal)
g4 = evaluation.gate_g4(comparison, coverage["coverage"])
print(json.dumps(g4, indent=2))
"""),
    md("## Per-aspect detection F1 / sentiment accuracy on the test split (target F1 ≥ 0.70)"),
    code("""
test_frame = cache["test"]["frame"]
aspects = evaluation.aspect_metrics(test_frame.aspects.tolist(), cache["test"]["aspects"])
aspects
"""),
    md("## G3 — full production pipeline on 10 reviews (target < 15 s each on CPU)"),
    code("""
from app.ml.pipeline import VERAPipeline

pipeline = VERAPipeline(paths.MODELS)
latencies = []
for row in test_frame.head(10).itertuples():
    started = time.perf_counter()
    pipeline.process(text=row.text, star_rating=float(row.rating))
    latencies.append(time.perf_counter() - started)
g3 = {"gate": "G3", "passed": max(latencies) < 15, "max_seconds": max(latencies),
      "mean_seconds": sum(latencies) / len(latencies)}
print(g3)
"""),
    code("""
report = {
    "cv_comparison": comparison,
    "test_interval": coverage,
    "conformal": conformal,
    "aspects": aspects.to_dict(orient="records"),
    "gates": {"G3": g3, "G4": g4},
    "aspect_f1_all_at_least_0_70": bool((aspects.detection_f1 >= 0.70).all()),
    "label_noise_reference": get_reference_agreement(
        json.loads(paths.AGREEMENT_REPORT.read_text())
    ),
}
(paths.REPORTS / "evaluation_report.json").write_text(json.dumps(report, indent=2, default=str))
print("Wrote", paths.REPORTS / "evaluation_report.json")
"""),
]


def main() -> None:
    for name, cells in NOTEBOOKS.items():
        notebook = new_notebook(
            cells=cells,
            metadata={
                "kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
                "language_info": {"name": "python"},
                **({"accelerator": "GPU", "colab": {"gpuType": "T4"}} if name.startswith("04") else {}),
            },
        )
        nbformat.validate(notebook)
        nbformat.write(notebook, HERE / f"{name}.ipynb")
        print("wrote", name)


if __name__ == "__main__":
    main()
