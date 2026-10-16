"""Generate notebooks/05_headphones_v2_pipeline.ipynb — crash-proof, ~1200 reviews."""

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook
from pathlib import Path

nb = new_notebook()

nb.cells = [
    new_markdown_cell("""# 🎧 Headphones Pipeline v2: Stream → Label → Fine-Tune → ONNX → HF Upload

**Improvements over v1:**
- ✅ **Google Drive checkpoint** — labels survive runtime crashes
- ✅ **~1,200 review target** — faster labeling, still sufficient for DeBERTa
- ✅ **Gemini Flash option** — much more reliable than Groq free tier
- ✅ **All-in-one** — single notebook does everything

**Runtime:** Google Colab with **T4 GPU** (*Runtime → Change runtime type → T4 GPU*)
"""),

    # ═══════════════════════════════════════════════════════════════════════════
    # CELL 1: Setup
    # ═══════════════════════════════════════════════════════════════════════════
    new_markdown_cell("## 1 · Setup Environment & Mount Google Drive"),

    new_code_cell("""# --- Cell 1: Environment Setup + Google Drive Mount ----------------------------
import os, sys, subprocess, zipfile, pathlib, shutil, time

# 1a. Mount Google Drive for crash-proof checkpoints
from google.colab import drive
drive.mount('/content/drive')

DRIVE_SAVE = pathlib.Path("/content/drive/MyDrive/vera_headphones")
DRIVE_SAVE.mkdir(exist_ok=True, parents=True)
print(f"✓ Google Drive mounted. Checkpoints saved to: {DRIVE_SAVE}")

# 1b. Install dependencies
subprocess.run([
    sys.executable, "-m", "pip", "install", "-q",
    "datasets", "accelerate", "transformers", "sentencepiece", "protobuf",
    "groq", "pydantic", "optimum[onnxruntime]", "onnx", "langdetect",
    "google-genai", "huggingface_hub",
], check=True)

# 1c. Unpack vera_colab_bundle.zip
ROOT = pathlib.Path("/content/vera")
OUT  = pathlib.Path("/content/headphone_colab_outputs")
OUT.mkdir(exist_ok=True, parents=True)

bundle_path = pathlib.Path("/content/vera_colab_bundle.zip")
if not bundle_path.exists():
    from google.colab import files
    print("Please upload 'vera_colab_bundle.zip':")
    uploaded = files.upload()
    for name in uploaded:
        if name.endswith(".zip"):
            bundle_path = pathlib.Path(f"/content/{name}")
            break

assert bundle_path.exists(), "vera_colab_bundle.zip not found!"
ROOT.mkdir(exist_ok=True, parents=True)
with zipfile.ZipFile(bundle_path) as z:
    z.extractall(ROOT)

os.chdir(ROOT)
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "training")]
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

# 1d. Symlink labels dir to Google Drive (crash-proof!)
drive_labels = DRIVE_SAVE / "labels"
drive_labels.mkdir(exist_ok=True, parents=True)
local_labels = ROOT / "data" / "labels"
if local_labels.exists() or local_labels.is_symlink():
    if local_labels.is_symlink():
        local_labels.unlink()
    else:
        shutil.rmtree(local_labels)
os.symlink(str(drive_labels), str(local_labels))
print(f"✓ Labels directory symlinked to Google Drive: {drive_labels}")

# 1e. Verify GPU
import torch
print(f"PyTorch: {torch.__version__}")
assert torch.cuda.is_available(), "Switch runtime to GPU (T4)!"
print(f"✓ GPU: {torch.cuda.get_device_name(0)}")
"""),

    # ═══════════════════════════════════════════════════════════════════════════
    # CELL 2: Stream Corpus
    # ═══════════════════════════════════════════════════════════════════════════
    new_markdown_cell("""## 2 · Stream & Filter Headphones Corpus
Streams from Hugging Face in-memory. Filters for Over-Ear / On-Ear headphones.
Samples **1,200 reviews** for labeling (star-stratified)."""),

    new_code_cell("""# --- Cell 2: Stream Corpus + Sample Labeling Pool (1200) ----------------------
import json, re, time, urllib.request
import pandas as pd
from huggingface_hub import hf_hub_url
from app.ml.agents.preprocessor import TextPreprocessor
from vera_training import paths
from vera_training.data import is_overear_headphone_product, sample_for_labeling
from vera_training.io import digest, validate_reviews

paths.ensure_dirs()
_PARENT_ASIN_RE = re.compile(r'"parent_asin":\\s*"([^"]+)"')

LABELING_POOL_SIZE = 1200  # ← reduced from 2000 for faster labeling

# Check if corpus already exists on Drive (skip re-streaming)
drive_corpus = DRIVE_SAVE / "headphone_reviews.parquet"
drive_pool   = DRIVE_SAVE / "headphone_labeling_pool.parquet"

if drive_corpus.exists() and drive_pool.exists():
    print("✓ Found cached corpus & pool on Google Drive, loading...")
    corpus = pd.read_parquet(drive_corpus)
    pool = pd.read_parquet(drive_pool)
    # Copy to expected paths
    corpus.to_parquet(paths.HEADPHONE_CORPUS, index=False)
    pool.to_parquet(paths.HEADPHONE_LABELING_POOL, index=False)
    print(f"  Corpus: {len(corpus):,} reviews | Pool: {len(pool)} reviews")
else:
    # Stream metadata
    def stream_headphone_metadata(max_products=15000):
        url = hf_hub_url(
            repo_id="McAuley-Lab/Amazon-Reviews-2023",
            filename="raw/meta_categories/meta_Electronics.jsonl",
            repo_type="dataset",
        )
        print("Connecting to metadata stream...", flush=True)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        products = {}
        scanned = 0
        start = time.time()
        with urllib.request.urlopen(req) as resp:
            for line in resp:
                scanned += 1
                try:
                    row = json.loads(line.decode("utf-8"))
                except Exception:
                    continue
                if is_overear_headphone_product(row):
                    asin = str(row.get("parent_asin") or "").strip()
                    title = str(row.get("title") or "").strip()
                    if asin and title:
                        products[asin] = title
                        if len(products) >= max_products:
                            break
                if scanned % 100000 == 0:
                    elapsed = time.time() - start
                    print(f"  Scanned {scanned:,} rows → {len(products):,} headphone ASINs ({scanned/elapsed:.0f} rows/s)", flush=True)
        print(f"✓ Found {len(products):,} headphone products in {time.time()-start:.1f}s")
        return products

    # Stream reviews
    def stream_headphone_reviews(products, target_reviews=50000, min_words=20):
        url = hf_hub_url(
            repo_id="McAuley-Lab/Amazon-Reviews-2023",
            filename="raw/review_categories/Electronics.jsonl",
            repo_type="dataset",
        )
        print(f"Connecting to reviews stream (target: {target_reviews:,})...", flush=True)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        asins = set(products.keys())
        cleaned, seen = [], set()
        scanned = 0
        start = time.time()
        with urllib.request.urlopen(req) as resp:
            for raw_line in resp:
                scanned += 1
                line = raw_line.decode("utf-8", errors="replace")
                match = _PARENT_ASIN_RE.search(line)
                if not match or match.group(1) not in asins:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                asin = match.group(1)
                if row.get("rating") not in (1, 2, 3, 4, 5, 1.0, 2.0, 3.0, 4.0, 5.0):
                    continue
                text = TextPreprocessor.clean_text(str(row.get("text") or ""))
                if len(text.split()) < min_words:
                    continue
                text_hash = digest(text.casefold())
                if text_hash in seen:
                    continue
                seen.add(text_hash)
                cleaned.append({
                    "review_id": digest([asin, text, row.get("timestamp"), row.get("user_id")]),
                    "parent_asin": asin,
                    "text": text,
                    "rating": float(row["rating"]),
                    "product_title": products[asin],
                    "helpful_vote": row.get("helpful_vote"),
                    "verified_purchase": row.get("verified_purchase"),
                    "timestamp": row.get("timestamp"),
                })
                if len(cleaned) % 5000 == 0:
                    elapsed = time.time() - start
                    print(f"  Collected {len(cleaned):,}/{target_reviews:,} ({len(cleaned)/elapsed:.1f} rev/s)", flush=True)
                if len(cleaned) >= target_reviews:
                    break
        df = pd.DataFrame(cleaned)
        validated = validate_reviews(df)
        print(f"✓ {len(validated):,} reviews across {validated.parent_asin.nunique():,} products in {time.time()-start:.1f}s")
        return validated

    headphone_products = stream_headphone_metadata(max_products=15000)
    corpus = stream_headphone_reviews(headphone_products, target_reviews=50000, min_words=20)
    corpus.to_parquet(paths.HEADPHONE_CORPUS, index=False)

    pool = sample_for_labeling(corpus, n=LABELING_POOL_SIZE, seed=42, product_cap=5, balanced_order=True)
    pool.to_parquet(paths.HEADPHONE_LABELING_POOL, index=False)

    # Cache to Drive so we don't re-stream after crashes
    corpus.to_parquet(drive_corpus, index=False)
    pool.to_parquet(drive_pool, index=False)
    print(f"✓ Saved corpus ({len(corpus):,}) and pool ({len(pool)}) to Google Drive")

print(f"\\nLabeling Pool Rating Distribution:")
print(pool.rating.value_counts().sort_index().to_string())
"""),

    # ═══════════════════════════════════════════════════════════════════════════
    # CELL 3: LLM Labeling (Gemini Flash or Groq)
    # ═══════════════════════════════════════════════════════════════════════════
    new_markdown_cell("""## 3 · Star-Blinded LLM Labeling
Choose your provider:
- **Gemini Flash** (recommended): Free, fast, reliable → get key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
- **Groq**: Free but heavily rate-limited on free tier

Labels are **checkpointed to Google Drive after every review** — crashes lose nothing!"""),

    new_code_cell("""# --- Cell 3: LLM Labeling with Live Progress + Drive Checkpoints -------------
import getpass, os, time, json
import pandas as pd
from vera_training import labeling, paths
from vera_training.io import atomic_json, digest

pool = pd.read_parquet(paths.HEADPHONE_LABELING_POOL)
checkpoint_file = paths.LABELS / "run_headphones_primary.json"

# Check existing progress
if checkpoint_file.exists():
    existing = json.loads(checkpoint_file.read_text())
    print(f"✓ Found existing checkpoint: {len(existing.get('labels', {}))}/{len(pool)} labeled")
else:
    print(f"Starting fresh: 0/{len(pool)} to label")

# ─── Choose Provider ──────────────────────────────────────────────────────────
print("\\n╔══════════════════════════════════════╗")
print("║  Choose your LLM labeling provider:  ║")
print("║  1 = Gemini Flash (recommended)      ║")
print("║  2 = Groq                            ║")
print("╚══════════════════════════════════════╝")
choice = input("Enter 1 or 2: ").strip()

if choice == "2":
    # --- Groq path ---
    if not os.environ.get("GROQ_API_KEY"):
        os.environ["GROQ_API_KEY"] = getpass.getpass("GROQ_API_KEY(s), comma-separated: ")
    keys = labeling.groq_keys_from_env()
    model_name = "qwen/qwen3.8-27b"
    provider_name = "groq"
    provider = labeling.GroqPool(model=model_name, api_keys=keys, max_tokens=900)
    rpm = 30
    print(f"Using Groq ({model_name}) with {len(keys)} key(s)")
else:
    # --- Gemini Flash path (default) ---
    if not os.environ.get("GEMINI_API_KEY"):
        os.environ["GEMINI_API_KEY"] = getpass.getpass("GEMINI_API_KEY: ")
    model_name = "gemini-2.0-flash"
    provider_name = "gemini"
    provider = labeling.Provider("gemini", model_name)
    rpm = 14  # Free tier: 15 RPM, keep 1 buffer
    print(f"Using Gemini Flash ({model_name})")

run_id = "headphones-primary"

# ─── Handle checkpoint model switch ───────────────────────────────────────────
if checkpoint_file.exists():
    state = json.loads(checkpoint_file.read_text())
    old_model = state["specification"].get("model", "")
    if old_model != model_name:
        print(f"⚠ Switching model from '{old_model}' → '{model_name}'")
        old_labels = dict(state["labels"])
        new_spec = {
            "provider": provider_name,
            "model": model_name,
            "run_id": run_id,
            "seed": 1,
            "prompt_hash": digest([labeling.SYSTEM_PROMPT, labeling.USER_PROMPT_TEMPLATE]),
            "input_hash": state["specification"]["input_hash"],
        }
        new_state = {
            "specification": new_spec,
            "requests": state["requests"],
            "labels": old_labels,
            "errors": {},
        }
        atomic_json(checkpoint_file, new_state)
        print(f"✓ Migrated {len(old_labels)} labels to new model checkpoint")

# ─── Live progress wrapper ────────────────────────────────────────────────────
existing_count = 0
if checkpoint_file.exists():
    existing_count = len(json.loads(checkpoint_file.read_text()).get("labels", {}))

progress_count = [existing_count]
start_time = time.time()

def progress_provider(system, prompt, seed):
    res = provider(system, prompt, seed)
    progress_count[0] += 1
    done = progress_count[0]
    total = len(pool)
    if done == existing_count + 1 or done % 10 == 0 or done == total:
        elapsed = time.time() - start_time
        new_done = done - existing_count
        rate = new_done / max(elapsed, 1)
        remaining = total - done
        eta_min = remaining / max(rate, 0.01) / 60
        print(f"  [{done:4d}/{total}] ({done/total*100:5.1f}%) | {rate:.2f} rev/s | ETA: {eta_min:.1f}m", flush=True)
    return res

# ─── Run labeling ─────────────────────────────────────────────────────────────
print(f"\\n{'='*60}")
print(f"Labeling {len(pool)} reviews with {model_name}")
print(f"Checkpoint: {checkpoint_file} (on Google Drive)")
print(f"{'='*60}\\n")

state = labeling.run_labels(
    pool,
    checkpoint_file,
    progress_provider,
    provider_name=provider_name,
    model=model_name,
    run_id=run_id,
    seed=1,
    max_requests=int(len(pool) * 1.5) + 100,
    requests_per_minute=rpm,
    retries=3,
)

labeled_count = len(state["labels"])
error_count = len(state.get("errors", {}))
print(f"\\n{'='*60}")
print(f"✅ Labeling done! {labeled_count}/{len(pool)} labeled, {error_count} errors")
print(f"{'='*60}")

if labeled_count < len(pool):
    print(f"\\n⚠ Only {labeled_count}/{len(pool)} labeled. Re-run this cell to resume!")
    print("Labels are safe on Google Drive — nothing is lost.")
"""),

    # ═══════════════════════════════════════════════════════════════════════════
    # CELL 4: Merge & Export Labels
    # ═══════════════════════════════════════════════════════════════════════════
    new_markdown_cell("""## 4 · Merge Labels & Export
Merges the LLM labels with review data and saves JSONL + CSV.
If labeling didn't reach 100%, this uses whatever we have."""),

    new_code_cell("""# --- Cell 4: Merge & Export Labels --------------------------------------------
import json, pathlib
import pandas as pd
from vera_training import labeling, paths
from vera_training.io import validate_reviews

pool = pd.read_parquet(paths.HEADPHONE_LABELING_POOL)
checkpoint_file = paths.LABELS / "run_headphones_primary.json"
state = json.loads(checkpoint_file.read_text())

labeled_ids = set(state["labels"].keys())
print(f"Total labeled: {len(labeled_ids)}/{len(pool)}")

# Build labeled dataframe (works even if < 100% complete)
rows = []
for review_id, label in state["labels"].items():
    validated = labeling.ExperienceLabel.model_validate(label)
    rows.append({"review_id": review_id, **validated.model_dump()})

labels_df = pd.DataFrame(rows)
labelled_df = pool[pool.review_id.isin(labeled_ids)].merge(labels_df, on="review_id", validate="one_to_one")
labelled_df = validate_reviews(labelled_df, labels=True)

# Save JSONL and CSV
labelled_df.to_json(paths.HEADPHONE_LABELS_V1, orient="records", lines=True)
csv_path = OUT / "headphone_labels_v1.csv"
labelled_df.to_csv(csv_path, index=False)

# Also save to Drive
labelled_df.to_json(DRIVE_SAVE / "headphone_labels_v1.jsonl", orient="records", lines=True)
labelled_df.to_csv(DRIVE_SAVE / "headphone_labels_v1.csv", index=False)

print(f"✓ Exported {len(labelled_df)} labeled reviews")
print(f"  → {paths.HEADPHONE_LABELS_V1}")
print(f"  → {csv_path}")
print(f"  → Google Drive: {DRIVE_SAVE / 'headphone_labels_v1.jsonl'}")

# Download to browser
from google.colab import files
try:
    files.download(str(csv_path))
except Exception:
    print("Auto-download failed. Download from Files panel or Google Drive.")

print(f"\\nScore distribution:")
print(labelled_df.experience_score.describe().to_string())
"""),

    # ═══════════════════════════════════════════════════════════════════════════
    # CELL 5: Fine-Tune DeBERTa
    # ═══════════════════════════════════════════════════════════════════════════
    new_markdown_cell("""## 5 · Fine-Tune DeBERTa-v3 + ONNX Export
Trains DeBERTa on the labeled reviews with 5-fold cross-validation, then:
- Trains a final model on 100% data
- Exports to ONNX (FP32 + INT8)
- Runs G2 parity checks"""),

    new_code_cell("""# --- Cell 5: Fine-Tune + ONNX Export ------------------------------------------
import json, shutil, pathlib
import pandas as pd
from vera_training.io import validate_reviews
from vera_training.finetune import FinetuneConfig, crossfit_predictions, train_final
from vera_training import paths

WORK = pathlib.Path("/content/headphone_work")
WORK.mkdir(exist_ok=True, parents=True)

# Load labeled data
labelled_rows = [json.loads(line) for line in paths.HEADPHONE_LABELS_V1.open(encoding="utf-8")]
labelled = validate_reviews(pd.DataFrame(labelled_rows), labels=True)
print(f"Fine-tuning on {len(labelled)} reviews across {labelled.parent_asin.nunique()} products")

# T4 GPU config
config = FinetuneConfig(max_length=512, epochs=3, train_batch_size=8)

# 5a. 5-Fold Cross-Validation for OOF predictions
print("\\n── 5-Fold Cross-Validation ──")
oof = crossfit_predictions(labelled, WORK / "crossfit", config, n_folds=5)
oof_df = pd.DataFrame({"review_id": labelled.review_id, "experience_raw": oof})
oof_path = OUT / "headphone_experience_oof.csv"
oof_df.to_csv(oof_path, index=False)
oof_mae = float((oof_df.experience_raw.clip(1, 5) - labelled.experience_score).abs().mean())
stars_mae = float((labelled.rating - labelled.experience_score).abs().mean())
print(f"\\n>>> OOF MAE: {oof_mae:.4f}  |  Stars MAE: {stars_mae:.4f} <<<")

# 5b. Train Final Model (100% data)
print("\\n── Training Final Model ──")
final_dir = WORK / "final" / "model"
if not (final_dir / "config.json").exists():
    final_dir = train_final(labelled, WORK / "final", config)

validation = json.loads((final_dir / "vera_training.json").read_text())["validation"]
print("Final validation:", validation)

model_out = OUT / "headphone_final_model"
shutil.copytree(final_dir, model_out, dirs_exist_ok=True)

# 5c. Export to ONNX + G2 Parity Check
print("\\n── ONNX Export ──")
from vera_training.export import export_experience

onnx_out = OUT / "onnx_model"
onnx_out.mkdir(exist_ok=True, parents=True)
sample_texts = labelled.text.iloc[:64].tolist()

export_report = export_experience(
    finetuned_dir=final_dir,
    out_dir=onnx_out,
    sample_texts=sample_texts,
    work_dir=WORK / "onnx_work",
    max_length=config.max_length,
)
print(f"✓ ONNX exported! G2 Parity: {'PASS ✅' if export_report['g2_passed'] else 'FAIL ❌'}")
print(f"  Model: {onnx_out / 'experience_model.onnx'} ({export_report['deployed_size_mb']} MB)")
print(f"  Precision: {export_report['deployed_precision']}")

# Save report to Drive
shutil.copytree(onnx_out, DRIVE_SAVE / "onnx_model", dirs_exist_ok=True)
print(f"✓ ONNX model backed up to Google Drive")
"""),

    # ═══════════════════════════════════════════════════════════════════════════
    # CELL 6: Package & Download
    # ═══════════════════════════════════════════════════════════════════════════
    new_markdown_cell("## 6 · Package Outputs & Download"),

    new_code_cell("""# --- Cell 6: Package & Download -----------------------------------------------
import shutil, pathlib
from google.colab import files
from vera_training import paths

# Copy key artifacts into output dir
shutil.copy(paths.HEADPHONE_CORPUS, OUT / "headphone_reviews.parquet")
if paths.HEADPHONE_LABELS_V1.exists():
    shutil.copy(paths.HEADPHONE_LABELS_V1, OUT / "headphone_labels_v1.jsonl")

for fname in ("experience_model.onnx", "experience_tokenizer.json", "experience_export_report.json"):
    src = OUT / "onnx_model" / fname
    if src.exists():
        shutil.copy(src, OUT / fname)

# Zip everything
archive = shutil.make_archive("/content/headphone_colab_outputs", "zip", OUT)
size_mb = pathlib.Path(archive).stat().st_size / 1e6
print(f"✓ Created: {archive} ({size_mb:.1f} MB)")

# Also copy zip to Drive
shutil.copy(archive, DRIVE_SAVE / "headphone_colab_outputs.zip")
print(f"✓ Backed up to Drive: {DRIVE_SAVE / 'headphone_colab_outputs.zip'}")

try:
    files.download(archive)
    print("Download started!")
except Exception:
    print("Download from Google Drive: " + str(DRIVE_SAVE / "headphone_colab_outputs.zip"))
"""),

    # ═══════════════════════════════════════════════════════════════════════════
    # CELL 7: Upload to HF Hub
    # ═══════════════════════════════════════════════════════════════════════════
    new_markdown_cell("## 7 · Upload ONNX Model to Hugging Face Hub"),

    new_code_cell("""# --- Cell 7: Upload to Hugging Face -------------------------------------------
from huggingface_hub import HfApi
import getpass, os

hf_token = os.environ.get("HF_TOKEN") or getpass.getpass("HF write token (hf_...): ")
repo_id = "RaviKishanKumar80/vera-models-headphones"

api = HfApi(token=hf_token)
api.create_repo(repo_id, repo_type="model", exist_ok=True, private=False)

print(f"Uploading to https://huggingface.co/{repo_id}...")

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
        print(f"  ✓ {fname}")

from vera_training import paths
for fname, src in [
    ("headphone_labels_v1.jsonl", paths.HEADPHONE_LABELS_V1),
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
        print(f"  ✓ {fname}")

print(f"\\n🎉 Uploaded to: https://huggingface.co/{repo_id}")
"""),
]

out_path = Path("notebooks/05_headphones_v2_pipeline.ipynb")
with open(out_path, "w", encoding="utf-8") as f:
    nbformat.write(nb, f)

print(f"✓ Created {out_path}")
