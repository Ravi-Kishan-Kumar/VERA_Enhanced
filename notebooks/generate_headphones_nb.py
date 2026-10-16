"""Generate notebooks/04_headphones_colab_pipeline.ipynb using nbformat."""

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook
from pathlib import Path

nb = new_notebook()

nb.cells = [
    new_markdown_cell("""# 🎧 Over-Ear / On-Ear Headphones: Stream, Label & Fine-Tune on Colab (GPU)
**Runs on:** Google Colab with a **T4 GPU** (free tier).
**Zero local disk requirement:** Streams directly from Hugging Face in memory, labels with LLMs, fine-tunes DeBERTa-v3, and packages outputs for 1-click download.

---

### End-to-End Pipeline Summary:
1. **Unpack & Setup:** Upload `vera_colab_bundle.zip` (only ~2.2 MB).
2. **Stream & Filter:** Stream reviews from `McAuley-Lab/Amazon-Reviews-2023` in memory. Filter for Over-Ear/On-Ear headphones and extract a 50,000-review corpus + 2,000-review balanced labeling pool.
3. **Star-Blinded Labeling:** Run LLM labeling (Groq `llama-3.3-70b-versatile` or Gemini) with automatic resume and rate-limit handling.
4. **Fine-Tune DeBERTa-v3:** Train DeBERTa on GPU for 3 epochs with 5-fold cross-fitting.
5. **Download:** Zip and download `headphone_colab_outputs.zip` containing the corpus, labels, out-of-fold predictions, and model weights.
"""),

    new_markdown_cell("## 1. Setup Environment & Unpack Bundle\nMake sure your runtime is set to **GPU (T4)**: *Runtime -> Change runtime type -> T4 GPU*."),

    new_code_cell("""# --- Environment Setup -------------------------------------------------------------
import os, sys, subprocess, zipfile, pathlib, shutil

ROOT = pathlib.Path("/content/vera")
OUT = pathlib.Path("/content/headphone_colab_outputs")
OUT.mkdir(exist_ok=True, parents=True)

# Install missing dependencies on Colab
subprocess.run([
    sys.executable, "-m", "pip", "install", "-q",
    "datasets", "accelerate", "transformers", "sentencepiece", "protobuf", "groq", "pydantic", "optimum[onnxruntime]", "onnx", "langdetect"
], check=True)



# Unpack vera_colab_bundle.zip
bundle_path = pathlib.Path("/content/vera_colab_bundle.zip")
if not bundle_path.exists():
    from google.colab import files
    print("Please upload 'vera_colab_bundle.zip' (from your project 'dist/' folder):")
    uploaded = files.upload()
    for name in uploaded:
        if name.endswith(".zip"):
            bundle_path = pathlib.Path(f"/content/{name}")
            break

assert bundle_path.exists(), "vera_colab_bundle.zip was not found!"
ROOT.mkdir(exist_ok=True, parents=True)
with zipfile.ZipFile(bundle_path) as z:
    z.extractall(ROOT)

os.chdir(ROOT)
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "training")]
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

import torch
print("PyTorch Version:", torch.__version__)
assert torch.cuda.is_available(), "Please switch the Colab runtime to GPU (T4)!"
print("Active GPU:", torch.cuda.get_device_name(0))
"""),

    new_markdown_cell("""## 2. Stream & Filter Headphones Corpus from Hugging Face
This streams directly from Hugging Face **without downloading the 20+ GB raw JSONL files**.
It captures Over-Ear & On-Ear headphones, applies text pre-processing, and samples a 2,000-review labeling pool."""),

    new_code_cell("""import json, re, time, urllib.request
import pandas as pd
from huggingface_hub import hf_hub_url
from app.ml.agents.preprocessor import TextPreprocessor
from vera_training import paths
from vera_training.data import is_overear_headphone_product, sample_for_labeling
from vera_training.io import digest, validate_reviews

paths.ensure_dirs()
_PARENT_ASIN_RE = re.compile(r'"parent_asin":\\s*"([^"]+)"')

# --- 1. Stream Metadata directly via HTTP (bypasses deprecated dataset scripts) ---
def stream_headphone_metadata(max_products=15000):
    url = hf_hub_url(
        repo_id="McAuley-Lab/Amazon-Reviews-2023",
        filename="raw/meta_categories/meta_Electronics.jsonl",
        repo_type="dataset",
    )
    print(f"Connecting to metadata stream...", flush=True)
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
                print(f"  Scanned {scanned:,} metadata rows -> found {len(products):,} headphone ASINs ({scanned/elapsed:.0f} rows/s)...", flush=True)
    print(f"Finished metadata stream: found {len(products):,} headphone products in {time.time()-start:.1f}s.\\n")
    return products

# --- 2. Stream Reviews directly via HTTP ---
def stream_headphone_reviews(products, target_reviews=50000, min_words=20):
    url = hf_hub_url(
        repo_id="McAuley-Lab/Amazon-Reviews-2023",
        filename="raw/review_categories/Electronics.jsonl",
        repo_type="dataset",
    )
    print(f"Connecting to reviews stream (target: {target_reviews:,} reviews)...", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    asins = set(products.keys())
    cleaned = []
    seen = set()
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
                print(f"  Collected {len(cleaned):,}/{target_reviews:,} reviews ({len(cleaned)/elapsed:.1f} rev/s)...", flush=True)
            if len(cleaned) >= target_reviews:
                break
    df = pd.DataFrame(cleaned)
    validated = validate_reviews(df)
    print(f"Finished review stream: {len(validated):,} reviews across {validated.parent_asin.nunique():,} products in {time.time()-start:.1f}s.\\n")
    return validated

# --- Execute Streaming Pipeline ---
headphone_products = stream_headphone_metadata(max_products=15000)
corpus = stream_headphone_reviews(headphone_products, target_reviews=50000, min_words=20)
corpus.to_parquet(paths.HEADPHONE_CORPUS, index=False)
print(f"Saved {len(corpus):,} reviews to {paths.HEADPHONE_CORPUS}")

# Draw star-stratified 2,000-review labeling pool
pool = sample_for_labeling(corpus, n=2000, seed=42, product_cap=5, balanced_order=True)
pool.to_parquet(paths.HEADPHONE_LABELING_POOL, index=False)
print("\\nLabeling Pool Rating Distribution:")
print(pool.rating.value_counts().sort_index().to_string())
"""),


    new_markdown_cell("""## 3. Star-Blinded LLM Labeling (Groq / Gemini)
Labels the 2,000 reviews with experience score (1.0–5.0), aspects sentiment, and sarcasm flag.
Enter your **GROQ_API_KEY** below. (Labeling uses Llama-3.3-70b-versatile or Llama-3.1-8b-instant)."""),

    new_code_cell("""import getpass, os
import pandas as pd
from vera_training import labeling, paths

# Set your Groq API key(s) - single key or multiple keys separated by comma
if not os.environ.get("GROQ_API_KEY"):
    raw_keys = getpass.getpass("Enter your GROQ_API_KEY (or multiple keys separated by commas): ").strip()
    os.environ["GROQ_API_KEY"] = raw_keys

keys = labeling.groq_keys_from_env()
print(f"Loaded {len(keys)} active Groq API key(s) for automatic rotation.")

pool = pd.read_parquet(paths.HEADPHONE_LABELING_POOL)
checkpoint_file = paths.LABELS / "run_headphones_primary.json"
model_name = "openai/gpt-oss-120b"
run_id = "headphones-primary"

print(f"Starting star-blinded labeling on {len(pool)} reviews with {model_name}...")
pool_runner = labeling.GroqPool(model=model_name, api_keys=keys)

# Live progress reporter wrapper
progress_count = 0
start_time = time.time()
def progress_provider(system, prompt, seed):
    global progress_count
    res = pool_runner(system, prompt, seed)
    progress_count += 1
    if progress_count == 1 or progress_count % 25 == 0 or progress_count == len(pool):
        elapsed = time.time() - start_time
        rate = progress_count / max(elapsed, 1)
        eta_min = (len(pool) - progress_count) / max(rate, 0.01) / 60
        print(f"  [{progress_count:4d}/{len(pool)}] ({progress_count/len(pool)*100:5.1f}%) | {rate:4.1f} rev/s | Elapsed: {elapsed/60:4.1f}m | ETA: {eta_min:4.1f}m", flush=True)
    return res

state = labeling.run_labels(
    pool,
    checkpoint_file,
    progress_provider,
    provider_name="groq",
    model=model_name,
    run_id=run_id,
    seed=1,
    max_requests=int(len(pool) * 1.5) + 50,
    requests_per_minute=600,
    retries=3,
)

print(f"\nLabeling finished! {len(state['labels'])} labeled reviews.")

# Merge pool reviews with LLM labels to create complete labeled dataset
from vera_training.labeling import merge_labels
labelled_df = merge_labels(pool, checkpoint_file)



# Save both JSONL (for pipeline training) and CSV (for Excel / inspection)
labelled_df.to_json(paths.HEADPHONE_LABELS_V1, orient="records", lines=True)
csv_path = OUT / "headphone_labels_v1.csv"
labelled_df.to_csv(csv_path, index=False)
print(f"✓ Saved {len(labelled_df)} validated labeled reviews to {paths.HEADPHONE_LABELS_V1}")
print(f"✓ Saved CSV export to {csv_path}")

# Trigger immediate browser download of the labeled dataset
from google.colab import files
try:
    print("Initiating automatic browser download of labeled dataset...")
    files.download(str(paths.HEADPHONE_LABELS_V1))
    files.download(str(csv_path))
except Exception:
    print("Download trigger failed. You can right-click the file in the Colab Files panel to download.")

"""),

    new_markdown_cell("""## 4. Fine-Tune DeBERTa-v3 on Colab GPU (5-Fold CV + Final Model)
Trains the DeBERTa-v3 model on the 2,000 labeled reviews with 512 token context, producing:
- `headphone_experience_oof.csv`: Out-of-fold predictions.
- `headphone_final_model/`: PyTorch model weights + tokenizer."""),

    new_code_cell("""import json, shutil
import pandas as pd
from vera_training.io import validate_reviews
from vera_training.finetune import FinetuneConfig, crossfit_predictions, train_final

WORK = pathlib.Path("/content/headphone_work")
WORK.mkdir(exist_ok=True, parents=True)

# Load validated headphone labels
labelled_rows = [json.loads(line) for line in paths.HEADPHONE_LABELS_V1.open(encoding="utf-8")]
labelled = validate_reviews(pd.DataFrame(labelled_rows), labels=True)
print(f"Fine-tuning on {len(labelled)} reviews across {labelled.parent_asin.nunique()} products...")

# T4 GPU Profile (512 tokens, AdamW, batch 8)
config = FinetuneConfig(max_length=512, epochs=3, batch_size=8)

# 1. 5-Fold Cross-Fitting for OOF predictions
print("Running 5-fold cross-validation...")
oof = crossfit_predictions(labelled, WORK / "crossfit", config, n_folds=5)
oof_df = pd.DataFrame({"review_id": labelled.review_id, "experience_raw": oof})
oof_path = OUT / "headphone_experience_oof.csv"
oof_df.to_csv(oof_path, index=False)
oof_mae = float((oof_df.experience_raw.clip(1, 5) - labelled.experience_score).abs().mean())
print(f"\\n>>> Headphones Out-Of-Fold MAE: {oof_mae:.4f} (Stars MAE: {(labelled.rating - labelled.experience_score).abs().mean():.4f}) <<<\\n")

# 2. Train Final Model on 100% of data
print("Training final full model checkpoint...")
final_dir = WORK / "final" / "model"
if not (final_dir / "config.json").exists():
    final_dir = train_final(labelled, WORK / "final", config)

validation = json.loads((final_dir / "vera_training.json").read_text())["validation"]
print("Final model validation stats:", validation)

# Copy model to output folder
model_out = OUT / "headphone_final_model"
shutil.copytree(final_dir, model_out, dirs_exist_ok=True)

# 3. Export to Production ONNX Graph & Run G2 Parity Check
print("\n>>> Exporting to Production ONNX Graph (FP32/INT8)...")
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
print("ONNX Export Successful! G2 Parity Passed:", export_report["g2_passed"])
print(f"ONNX Model: {onnx_out / 'experience_model.onnx'} ({export_report['deployed_size_mb']} MB)")
"""),

    new_markdown_cell("""## 5. Package Outputs & One-Click Download
Copies the ONNX model, corpus parquet, frozen labels, and OOF predictions into a zip archive and triggers browser download."""),

    new_code_cell("""import shutil
from google.colab import files

# Copy corpus parquet, labels, and ONNX artifacts into output directory
shutil.copy(paths.HEADPHONE_CORPUS, OUT / "headphone_reviews.parquet")
shutil.copy(paths.HEADPHONE_LABELS_V1, OUT / "headphone_labels_v1.jsonl")

# Copy ONNX artifacts to root of OUT for easy access
for fname in ("experience_model.onnx", "experience_tokenizer.json", "experience_export_report.json"):
    src = onnx_out / fname
    if src.exists():
        shutil.copy(src, OUT / fname)

# Create zip archive
archive_path = shutil.make_archive("/content/headphone_colab_outputs", "zip", OUT)
print("Created zip bundle:", archive_path)
print(f"Size: {pathlib.Path(archive_path).stat().st_size / 1e6:.1f} MB")

# Trigger automatic browser download
try:
    files.download(archive_path)
    print("Download started! Check your browser downloads.")
except Exception as e:
    print("Download trigger failed. You can right-click '/content/headphone_colab_outputs.zip' in the Files tab on the left to download.")
"""),

    new_markdown_cell("""## 6. 🚀 Upload ONNX Model Directly to Hugging Face Hub
Uploads the **production-ready ONNX model** (`experience_model.onnx`, `experience_tokenizer.json`, and metadata) directly to your Hugging Face repository!"""),

    new_code_cell("""# --- Upload ONNX Model to Hugging Face Hub -------------------------------------
from huggingface_hub import HfApi
import getpass, os

hf_token = os.environ.get("HF_TOKEN") or getpass.getpass("Enter your Hugging Face write token (hf_...): ").strip()
repo_id = "RaviKishanKumar80/vera-models-headphones"

api = HfApi(token=hf_token)
api.create_repo(repo_id, repo_type="model", exist_ok=True, private=False)

print(f"Uploading ONNX model & artifacts to https://huggingface.co/{repo_id}...")

# 1. Upload the ONNX model files
for fname in ("experience_model.onnx", "experience_tokenizer.json", "experience_export_report.json"):
    fpath = onnx_out / fname
    if fpath.exists():
        api.upload_file(
            path_or_fileobj=str(fpath),
            path_in_repo=fname,
            repo_id=repo_id,
            repo_type="model",
            commit_message=f"Add ONNX {fname}",
        )
        print(f"  ✓ Uploaded {fname}")

# 2. Upload the labeled dataset and OOF predictions
for fname, src_path in [
    ("headphone_labels_v1.jsonl", paths.HEADPHONE_LABELS_V1),
    ("headphone_experience_oof.csv", OUT / "headphone_experience_oof.csv"),
]:
    if src_path.exists():
        api.upload_file(
            path_or_fileobj=str(src_path),
            path_in_repo=fname,
            repo_id=repo_id,
            repo_type="model",
            commit_message=f"Add {fname}",
        )
        print(f"  ✓ Uploaded {fname}")

print(f"\n🎉 Successfully uploaded the ONNX model suite to: https://huggingface.co/{repo_id}")
""")

]

out_path = Path("notebooks/04_headphones_colab_pipeline.ipynb")

with open(out_path, "w", encoding="utf-8") as f:
    nbformat.write(nb, f)

print(f"Created {out_path} successfully!")
