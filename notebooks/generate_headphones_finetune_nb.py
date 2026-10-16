"""Generate notebooks/06_headphones_finetune.ipynb

Lean post-labeling pipeline:
  1. Setup + unpack bundle (which already contains run_headphones_primary.json)
  2. Stream corpus + rebuild labeling pool (needed to match review text to label IDs)
  3. Merge frozen labels -> labelled_df
  4. Fine-tune DeBERTa-v3 (5-fold CV + final model)
  5. ONNX export + G2 parity check
  6. Package + download
  7. Upload to HuggingFace
"""

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook
from pathlib import Path

nb = new_notebook()

nb.cells = [

    new_markdown_cell("""\
# Headphones Fine-Tune Pipeline (Labels Already Done)

**1,222 frozen labels are bundled -- no labeling step needed.**

Pipeline:
1. Setup & unpack bundle
2. Stream corpus + rebuild 1,200-review pool (to recover review text)
3. Merge frozen labels
4. Fine-tune DeBERTa-v3 (5-fold CV + final)
5. ONNX export + G2 parity
6. Download outputs
7. Upload to Hugging Face

**Runtime:** T4 GPU (*Runtime -> Change runtime type -> T4 GPU*)
"""),

    new_markdown_cell("## 1 . Setup"),

    new_code_cell("""\
import os, sys, subprocess, zipfile, pathlib, shutil

ROOT = pathlib.Path("/content/vera")
OUT  = pathlib.Path("/content/headphone_outputs")
OUT.mkdir(exist_ok=True, parents=True)

subprocess.run([
    sys.executable, "-m", "pip", "install", "-q",
    "datasets", "accelerate", "transformers", "sentencepiece", "protobuf",
    "pydantic", "optimum[onnxruntime]", "onnx", "langdetect", "huggingface_hub",
], check=True)

bundle_path = pathlib.Path("/content/vera_colab_bundle.zip")
if not bundle_path.exists():
    from google.colab import files
    print("Upload vera_colab_bundle.zip:")
    uploaded = files.upload()
    for name in uploaded:
        if name.endswith(".zip"):
            bundle_path = pathlib.Path(f"/content/{name}")
            break

assert bundle_path.exists(), "vera_colab_bundle.zip not found!"
ROOT.mkdir(exist_ok=True, parents=True)
with zipfile.ZipFile(bundle_path) as z:
    z.extractall(ROOT)

print("Bundle contents (data/):")
for p in sorted((ROOT / "data").rglob("*")):
    if p.is_file():
        print(f"  {p.relative_to(ROOT)}  ({p.stat().st_size:,} bytes)")

os.chdir(ROOT)
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "training")]
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL",    "redis://localhost:6379/0")

import torch
assert torch.cuda.is_available(), "Switch runtime to GPU (T4)!"
print(f"GPU: {torch.cuda.get_device_name(0)}")
"""),

    new_markdown_cell("""\
## 2 . Stream Corpus & Rebuild Labeling Pool

The checkpoint (`run_headphones_primary.json`) stores `review_id -> label`.
We stream the corpus to recover the actual review text for each ID.
Takes about **5-15 minutes** depending on Colab network speed.
"""),

    new_code_cell("""\
import json, re, time, urllib.request
import pandas as pd
from huggingface_hub import hf_hub_url
from app.ml.agents.preprocessor import TextPreprocessor
from vera_training import paths
from vera_training.data import is_overear_headphone_product, sample_for_labeling
from vera_training.io import digest, validate_reviews

paths.ensure_dirs()

checkpoint_file = paths.LABELS / "run_headphones_primary.json"
assert checkpoint_file.exists(), f"Checkpoint not found: {checkpoint_file}"
state = json.loads(checkpoint_file.read_text(encoding="utf-8"))
labeled_ids = set(state["labels"].keys())
print(f"Frozen labels: {len(labeled_ids)} reviews")
print(f"Model used:    {state['specification']['model']}")

_ASIN_RE = re.compile(r'"parent_asin":\\s*"([^"]+)"')

def stream_headphone_metadata(max_products=15000):
    url = hf_hub_url(
        repo_id="McAuley-Lab/Amazon-Reviews-2023",
        filename="raw/meta_categories/meta_Electronics.jsonl",
        repo_type="dataset",
    )
    print("Streaming metadata...", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    products = {}
    scanned = 0
    t0 = time.time()
    with urllib.request.urlopen(req) as resp:
        for line in resp:
            scanned += 1
            try:
                row = json.loads(line.decode("utf-8"))
            except Exception:
                continue
            if is_overear_headphone_product(row):
                asin  = str(row.get("parent_asin") or "").strip()
                title = str(row.get("title") or "").strip()
                if asin and title:
                    products[asin] = title
                    if len(products) >= max_products:
                        break
            if scanned % 100_000 == 0:
                print(f"  {scanned:,} rows -> {len(products):,} ASINs ({scanned/(time.time()-t0):.0f}/s)", flush=True)
    print(f"Done: {len(products):,} products in {time.time()-t0:.1f}s")
    return products

def stream_headphone_reviews(products, target=50_000, min_words=20):
    url = hf_hub_url(
        repo_id="McAuley-Lab/Amazon-Reviews-2023",
        filename="raw/review_categories/Electronics.jsonl",
        repo_type="dataset",
    )
    print(f"Streaming reviews (target {target:,})...", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    asins = set(products)
    cleaned, seen = [], set()
    t0 = time.time()
    with urllib.request.urlopen(req) as resp:
        for raw in resp:
            line = raw.decode("utf-8", errors="replace")
            m = _ASIN_RE.search(line)
            if not m or m.group(1) not in asins:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            asin = m.group(1)
            if row.get("rating") not in (1, 2, 3, 4, 5, 1., 2., 3., 4., 5.):
                continue
            text = TextPreprocessor.clean_text(str(row.get("text") or ""))
            if len(text.split()) < min_words:
                continue
            h = digest(text.casefold())
            if h in seen:
                continue
            seen.add(h)
            cleaned.append({
                "review_id":         digest([asin, text, row.get("timestamp"), row.get("user_id")]),
                "parent_asin":       asin,
                "text":              text,
                "rating":            float(row["rating"]),
                "product_title":     products[asin],
                "helpful_vote":      row.get("helpful_vote"),
                "verified_purchase": row.get("verified_purchase"),
                "timestamp":         row.get("timestamp"),
            })
            if len(cleaned) % 5000 == 0:
                print(f"  {len(cleaned):,}/{target:,} ({len(cleaned)/(time.time()-t0):.1f} rev/s)", flush=True)
            if len(cleaned) >= target:
                break
    df = validate_reviews(pd.DataFrame(cleaned))
    print(f"Done: {len(df):,} reviews in {time.time()-t0:.1f}s")
    return df

products = stream_headphone_metadata()
corpus   = stream_headphone_reviews(products, target=50_000)
corpus.to_parquet(paths.HEADPHONE_CORPUS, index=False)

# Rebuild pool with SAME seed/params used during original labeling
pool = sample_for_labeling(corpus, n=1200, seed=42, product_cap=5, balanced_order=True)
pool.to_parquet(paths.HEADPHONE_LABELING_POOL, index=False)

matched = len(set(pool.review_id) & labeled_ids)
print(f"Pool: {len(pool)} reviews | Labels matched: {matched}/{len(labeled_ids)}")
if matched < len(labeled_ids) * 0.9:
    print("WARNING: fewer matches than expected!")
"""),

    new_markdown_cell("## 3 . Merge Frozen Labels"),

    new_code_cell("""\
import json
import pandas as pd
from vera_training import labeling, paths
from vera_training.io import validate_reviews

pool            = pd.read_parquet(paths.HEADPHONE_LABELING_POOL)
checkpoint_file = paths.LABELS / "run_headphones_primary.json"
state           = json.loads(checkpoint_file.read_text(encoding="utf-8"))

label_rows = [
    {"review_id": rid, **labeling.ExperienceLabel.model_validate(raw).model_dump()}
    for rid, raw in state["labels"].items()
]
labels_df = pd.DataFrame(label_rows)

labeled_pool = pool[pool.review_id.isin(labels_df.review_id)]
labelled_df  = labeled_pool.merge(labels_df, on="review_id", validate="one_to_one")
labelled_df  = validate_reviews(labelled_df, labels=True)

print(f"Training samples:  {len(labelled_df)}")
print(f"Products covered:  {labelled_df.parent_asin.nunique()}")
print(f"Experience score distribution:")
print(labelled_df.experience_score.value_counts().sort_index().to_string())

labelled_df.to_json(paths.HEADPHONE_LABELS_V1, orient="records", lines=True)
labelled_df.to_csv(OUT / "headphone_labels_v1.csv", index=False)
print(f"Saved: {paths.HEADPHONE_LABELS_V1}")
"""),

    new_markdown_cell("""\
## 4 . Fine-Tune DeBERTa-v3

- **5-fold CV** -> out-of-fold (OOF) predictions
- **Final model** on 100% data
- Each fold checkpoints to disk -- safe to re-run on Colab disconnect.
"""),

    new_code_cell("""\
import json, shutil, pathlib
import pandas as pd
from vera_training.io import validate_reviews
from vera_training.finetune import FinetuneConfig, crossfit_predictions, train_final
from vera_training import paths

WORK = pathlib.Path("/content/headphone_work")
WORK.mkdir(exist_ok=True, parents=True)

labelled_rows = [json.loads(l) for l in paths.HEADPHONE_LABELS_V1.open(encoding="utf-8")]
labelled = validate_reviews(pd.DataFrame(labelled_rows), labels=True)
print(f"Training: {len(labelled)} reviews | {labelled.parent_asin.nunique()} products")

config = FinetuneConfig(max_length=512, epochs=3, train_batch_size=8)

# 5-fold OOF
print("\\n[1/2] 5-Fold Cross-Validation ...")
oof = crossfit_predictions(labelled, WORK / "crossfit", config, n_folds=5)

oof_df = pd.DataFrame({"review_id": labelled.review_id, "experience_raw": oof})
oof_df.to_csv(OUT / "headphone_experience_oof.csv", index=False)

oof_mae   = float((oof_df.experience_raw.clip(1, 5) - labelled.experience_score).abs().mean())
stars_mae = float((labelled.rating - labelled.experience_score).abs().mean())
print(f"\\n>>> OOF MAE: {oof_mae:.4f}  |  Stars-as-proxy MAE: {stars_mae:.4f} <<<")

# Final model
print("\\n[2/2] Training Final Model ...")
final_dir = WORK / "final" / "model"
if not (final_dir / "config.json").exists():
    final_dir = train_final(labelled, WORK / "final", config)

val_stats = json.loads((final_dir / "vera_training.json").read_text())["validation"]
print("Validation:", val_stats)

shutil.copytree(final_dir, OUT / "headphone_final_model", dirs_exist_ok=True)
print("Model saved.")
"""),

    new_markdown_cell("## 5 . ONNX Export + G2 Parity Check"),

    new_code_cell("""\
import json, pathlib
import pandas as pd
from vera_training.export import export_experience
from vera_training.io import validate_reviews
from vera_training.finetune import FinetuneConfig
from vera_training import paths

config    = FinetuneConfig(max_length=512)
final_dir = pathlib.Path("/content/headphone_work/final/model")
onnx_out  = OUT / "onnx_model"
onnx_out.mkdir(exist_ok=True, parents=True)

labelled_rows = [json.loads(l) for l in paths.HEADPHONE_LABELS_V1.open(encoding="utf-8")]
labelled      = validate_reviews(pd.DataFrame(labelled_rows), labels=True)
sample_texts  = labelled.text.iloc[:64].tolist()

print("Exporting to ONNX ...")
report = export_experience(
    finetuned_dir=final_dir,
    out_dir=onnx_out,
    sample_texts=sample_texts,
    work_dir=pathlib.Path("/content/headphone_work/onnx_work"),
    max_length=config.max_length,
)

print(f"G2 Parity:  {'PASS' if report['g2_passed'] else 'FAIL'}")
print(f"Precision:  {report['deployed_precision']}  ({report['deployed_size_mb']} MB)")
print(f"FP32 max|delta|: {report['fp32_max_abs_diff']:.6f}  (threshold 0.01)")

if not report["g2_passed"]:
    raise AssertionError("G2 parity failed!")
print("ONNX export complete.")
"""),

    new_markdown_cell("## 6 . Package & Download"),

    new_code_cell("""\
import shutil, pathlib
from google.colab import files
from vera_training import paths

shutil.copy(paths.HEADPHONE_CORPUS,    OUT / "headphone_reviews.parquet")
shutil.copy(paths.HEADPHONE_LABELS_V1, OUT / "headphone_labels_v1.jsonl")

for fname in ("experience_model.onnx", "experience_tokenizer.json", "experience_export_report.json"):
    src = OUT / "onnx_model" / fname
    if src.exists():
        shutil.copy(src, OUT / fname)

archive = shutil.make_archive("/content/headphone_outputs", "zip", OUT)
size_mb = pathlib.Path(archive).stat().st_size / 1e6
print(f"Archive: {archive}  ({size_mb:.1f} MB)")

try:
    files.download(archive)
    print("Download started!")
except Exception:
    print("Download from Files panel: /content/headphone_outputs.zip")
"""),

    new_markdown_cell("## 7 . Upload to Hugging Face Hub"),

    new_code_cell("""\
from huggingface_hub import HfApi
import getpass, os
from vera_training import paths

hf_token = os.environ.get("HF_TOKEN") or getpass.getpass("HF write token (hf_...): ").strip()
repo_id  = "RaviKishanKumar80/vera-models-headphones"

api = HfApi(token=hf_token)
api.create_repo(repo_id, repo_type="model", exist_ok=True, private=False)
print(f"Uploading to https://huggingface.co/{repo_id}")

for fname in ("experience_model.onnx", "experience_tokenizer.json", "experience_export_report.json"):
    fpath = OUT / "onnx_model" / fname
    if fpath.exists():
        api.upload_file(
            path_or_fileobj=str(fpath),
            path_in_repo=fname,
            repo_id=repo_id,
            repo_type="model",
            commit_message=f"Add {fname}",
        )
        print(f"  uploaded: {fname}")

for fname, src in [
    ("headphone_labels_v1.jsonl",    paths.HEADPHONE_LABELS_V1),
    ("headphone_experience_oof.csv", OUT / "headphone_experience_oof.csv"),
]:
    if src.exists():
        api.upload_file(
            path_or_fileobj=str(src),
            path_in_repo=fname,
            repo_id=repo_id,
            repo_type="model",
            commit_message=f"Add {fname}",
        )
        print(f"  uploaded: {fname}")

print(f"\\nDone! https://huggingface.co/{repo_id}")
"""),
]

out_path = Path("notebooks/06_headphones_finetune.ipynb")
with open(out_path, "w", encoding="utf-8") as f:
    nbformat.write(nb, f)

print(f"Created {out_path}")
