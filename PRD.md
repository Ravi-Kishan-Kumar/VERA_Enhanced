# VERA — Verified Experience & Review Analyzer
## Product Requirements Document (PRD) v1.2
> **Author:** Rakshak S (Loki) · **Status:** APPROVED FOR BUILD · **Date:** September 2026

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Solution Overview](#3-solution-overview)
4. [Pre-Requisites & Environment Setup](#4-pre-requisites--environment-setup)
5. [Repository Structure](#5-repository-structure)
6. [Dataset Strategy](#6-dataset-strategy)
7. [Labeling Protocol — Gemini Flash](#7-labeling-protocol--gemini-flash)
8. [System Architecture](#8-system-architecture)
9. [Agent Specifications](#9-agent-specifications)
10. [Fusion & Calibration Layer](#10-fusion--calibration-layer)
11. [Product Aggregation — Empirical Bayes](#11-product-aggregation--empirical-bayes)
12. [Model Fine-tuning Guide (Colab)](#12-model-fine-tuning-guide-colab)
13. [Evaluation Protocol](#13-evaluation-protocol)
14. [API Design](#14-api-design)
15. [Database Schema](#15-database-schema)
16. [Frontend Design System](#16-frontend-design-system)
17. [Deployment Architecture](#17-deployment-architecture)
18. [CI/CD Pipeline](#18-cicd-pipeline)
19. [Claude ↔ Codex Handoff Protocol](#19-claude--codex-handoff-protocol)
20. [Phased Roadmap](#20-phased-roadmap)
21. [Weakness Resolution Matrix](#21-weakness-resolution-matrix)
22. [Success Criteria](#22-success-criteria)
23. [Implementation Corrections (v1.2)](#23-implementation-corrections-v12)

---

## 1. Executive Summary

VERA replaces dishonest star ratings with a **multi-signal, calibrated experience score** derived from seven specialized extraction agents, an XGBoost bootstrap ensemble, split-conformal calibration, and Empirical Bayes product aggregation.

**What it does:**
- Takes any Amazon product review (text + star + metadata) as input
- Produces a corrected experience score (1–5) that reflects what the reviewer actually experienced — not the star they clicked
- Provides a calibrated uncertainty interval with verified empirical coverage
- Extracts per-aspect sentiment across 10 earbud-specific dimensions
- Aggregates across reviews at product level, shrinking unreliable estimates toward the global mean

**Why it matters:**
- 54.7% of Amazon earbud reviews are 5-star; stars are inflated and untrustworthy
- Stars and text match in only ~55.5% of reviews
- One 5.0-star product beats a 4.6-star product with 500 reviews under the current ranking system
- VERA corrects all three failures with a production-grade, academically defensible system

**Key numbers from prior work (to beat):**
- Stars-only baseline MAE: `0.502 ± 0.050`
- VERA target MAE: `< 0.455 ± 0.032` (domain rating feature confirmed)
- Fold win rate target: `> 93%`

---

## 2. Problem Statement

Online star ratings are the primary signal of product quality on Amazon, but they systematically misrepresent what customers actually experienced.

### 2.1 The Three Failures

| Failure | Evidence |
|---|---|
| **Rating inflation** | 54.7% of 200,202 cleaned earbud reviews are 5-star |
| **Star-text disagreement** | Stars match text-derived score in only 55.5% of reviews; mean absolute gap = 0.50 |
| **Hidden aspect detail** | A 4-star review might mean excellent sound and terrible battery — the star tells you nothing |
| **Broken product ranking** | One 5.0 review beats 500 reviews averaging 4.6 |

### 2.2 Who This Affects

- **Shoppers** — can't trust the stars to reflect actual product quality
- **Sellers** — can't identify which specific aspects to improve
- **Platforms** — rankings mislead users, eroding trust

### 2.3 Core Difficulty: No Ground Truth

"Experience" is latent. Stars are exactly what we distrust, so they cannot be the label. Labels must be constructed, their reliability measured, and the model's error compared against that noise floor. This is the central challenge that makes this problem hard and interesting.

---

## 3. Solution Overview

### 3.1 What VERA Produces (per review)

```
Input:  review_text + star_rating + helpful_votes + verified_purchase + product_title
Output: {
  corrected_score:    float [1.0, 5.0],
  confidence_interval: [lower, upper],      # 90% empirical coverage guaranteed
  confidence_value:   float [0, 1],         # calibrated, not fake
  aspect_sentiment: {
    sound_quality:    { detected: bool, sentiment: pos/neg/neutral },
    bass:             { detected: bool, sentiment: pos/neg/neutral },
    battery_life:     { detected: bool, sentiment: pos/neg/neutral },
    comfort:          { detected: bool, sentiment: pos/neg/neutral },
    fit:              { detected: bool, sentiment: pos/neg/neutral },
    build_quality:    { detected: bool, sentiment: pos/neg/neutral },
    connectivity:     { detected: bool, sentiment: pos/neg/neutral },
    microphone:       { detected: bool, sentiment: pos/neg/neutral },
    noise_cancellation:{ detected: bool, sentiment: pos/neg/neutral },
    value:            { detected: bool, sentiment: pos/neg/neutral }
  },
  star_text_gap:      float,   # how much star disagrees with text
  review_quality:     float    # trust weight for product aggregation
}
```

### 3.2 What VERA Produces (per product)

```
product_corrected_score:    float [1.0, 5.0]   # EB-shrunk aggregate
product_uncertainty:        float               # spread across reviews
review_count:               int
trust_weighted_score:       float               # quality-weighted mean
aspect_breakdown:           dict                # per-aspect aggregated sentiment
ranking_position:           int                 # rank among all products
```

### 3.3 System Name Etymology

**V**erified **E**xperience & **R**eview **A**nalyzer — because the only signal we trust is what the reviewer actually said, verified by multiple independent models, never the star they clicked.

---

## 4. Pre-Requisites & Environment Setup

> **Read this section completely before touching any code.** Every tool here must be installed before Phase 1 begins.

### 4.1 System Requirements

| Requirement | Minimum | Recommended |
|---|---|---|
| Python | 3.11 | 3.12 |
| Node.js | 18 LTS | 20 LTS |
| RAM | 8 GB | 16 GB |
| Disk | 30 GB | 50 GB (for dataset) |
| OS | Ubuntu 22.04 / macOS 13 | Ubuntu 24.04 |

### 4.2 VS Code Extensions (Install First)

Open VS Code → Extensions (`Ctrl+Shift+X`) → search and install:

```
ms-python.python              # Python language support
ms-toolsai.jupyter            # Jupyter notebook support
ms-toolsai.vscode-jupyter-slideshow
iterative.colab               # Google Colab runtime connection
GitHub.copilot                # Codex (if using Copilot)
ms-azuretools.vscode-docker   # Docker integration
eamodio.gitlens               # Git history
bradlc.vscode-tailwindcss     # Tailwind IntelliSense
```

**Connecting VS Code to Colab GPU:**
1. Install `iterative.colab` extension
2. In Colab: `Tools → Settings → Enable third-party cookies`
3. In Colab notebook cell: run the connection snippet (provided in §12)
4. In VS Code: `Ctrl+Shift+P` → `Jupyter: Specify local or remote Jupyter server` → paste Colab URL

### 4.3 Accounts to Create (All Free)

| Service | URL | What For | Free Tier |
|---|---|---|---|
| **Supabase** | supabase.com | PostgreSQL database | 500MB, unlimited API |
| **Upstash** | upstash.com | Redis (queue + cache) | 10K commands/day |
| **Render** | render.com | Backend + workers | 750 hrs/month |
| **Vercel** | vercel.com | Next.js frontend | Unlimited for hobby |
| **HuggingFace** | huggingface.co | Model storage + Hub | Free |
| **Google AI Studio** | aistudio.google.com | Gemini Flash API (labeling) | 1M tokens/day |
| **UptimeRobot** | uptimerobot.com | Keep Render alive | 50 monitors free |
| **Google Colab** | colab.research.google.com | GPU fine-tuning | Free T4 GPU |
| **GitHub** | github.com | Repo + CI/CD | Free |

### 4.4 Python Environment Setup

> **v1.1 correction:** Python **3.12 only**. MAPIE moved to dev requirements; `pydantic-settings` + `huggingface_hub` added to production; test extras in `backend/requirements-test.txt`. `LightTokenizer` loads the local `tokenizer.json` shipped with each ONNX model and pads dynamically — see `backend/app/ml/models/tokenizer_wrapper.py`. (§23 #1–3)

> **Critical separation:** `requirements.txt` is the **production** file — no
> PyTorch, no `transformers`.  Loading either library in the Render worker
> consumes ~350 MB before a single model is touched, which overflows the
> 512 MB free-tier ceiling.  Production inference uses `onnxruntime` +
> `tokenizers` (Rust-based HuggingFace tokenizer library, zero torch dep).
> `requirements-dev.txt` adds torch + transformers for notebooks and fine-tuning.

```bash
git clone https://github.com/YOUR_USERNAME/vera
cd vera
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# ── requirements.txt (production — deploy this to Render) ─────────────
# Inference (no torch, no transformers)
pip install onnxruntime==1.19.0
pip install tokenizers==0.20.0          # Rust tokenizer, no torch dep

# Language detection
pip install langdetect==1.0.9           # pure Python, replaces fasttext

# ML / signal agents
pip install scikit-learn==1.5.2
pip install xgboost==2.1.1
pip install mapie==0.8.6                # conformal prediction
pip install joblib==1.4.2

# API / worker
pip install fastapi==0.115.0
pip install uvicorn[standard]==0.31.0
pip install celery==5.4.0
pip install redis==5.1.1
pip install sqlalchemy==2.0.35
pip install alembic==1.13.3
pip install psycopg2-binary==2.9.9
pip install pydantic==2.9.2
pip install python-dotenv==1.0.1
pip install httpx==0.27.2

# Data
pip install numpy==1.26.4
pip install pandas==2.2.3
pip install pyarrow==17.0.0

# Testing (include in production image for health-check assertions)
pip install pytest==8.3.3
pip install pytest-asyncio==0.24.0

pip freeze > requirements.txt

# ── requirements-dev.txt (development + fine-tuning, Colab only) ──────
pip install torch==2.4.0 --index-url https://download.pytorch.org/whl/cpu
pip install transformers==4.45.0
pip install datasets==3.0.0
pip install onnx==1.16.0
pip install optimum[exporters]==1.21.0   # ONNX export
pip install accelerate==0.34.0           # Trainer acceleration
pip install google-generativeai==0.7.2   # Gemini Flash labeling
pip install groq==0.11.0                 # Groq fallback
pip install scipy==1.14.1
pip install matplotlib==3.9.2
pip install seaborn==0.13.2
pip install black==24.10.0
pip install ruff==0.6.9

pip freeze > requirements-dev.txt
```

**Production tokenizer wrapper (no `transformers` import):**

```python
# backend/app/ml/models/tokenizer_wrapper.py
#
# Drop-in replacement for AutoTokenizer that has no torch dependency.
# The HuggingFace `tokenizers` library is a Rust binary (~5 MB) that
# reads the same tokenizer.json files transformers downloads — but it
# never imports torch.

import numpy as np
from tokenizers import Tokenizer
from tokenizers.processors import TemplateProcessing

class LightTokenizer:
    """Rust-backed tokenizer. Works with any model that ships tokenizer.json."""

    def __init__(self, model_name_or_path: str, max_length: int = 512):
        self._tok = Tokenizer.from_pretrained(model_name_or_path)
        self._max_length = max_length
        self._tok.enable_padding(pad_id=0, pad_token='[PAD]', length=max_length)
        self._tok.enable_truncation(max_length=max_length)

    def __call__(self, text: str, text_pair: str = None) -> dict:
        enc = self._tok.encode(text, text_pair)
        return {
            'input_ids':      np.array([enc.ids],          dtype=np.int64),
            'attention_mask': np.array([enc.attention_mask], dtype=np.int64),
            'token_type_ids': np.array([enc.type_ids],     dtype=np.int64),
        }
```

Replace every `AutoTokenizer.from_pretrained(...)` in the production agents
with `LightTokenizer(...)` using the same model name.

### 4.5 Node.js / Frontend Setup

> **v1.1 correction:** Frontend runs Next.js 16 / React 19 with TypeScript 6.0.3 and ESLint 9; components are hand-written (no shadcn/d3). (§23 #25)

```bash
# Install Node 20 (use nvm for easy version management)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.0/install.sh | bash
nvm install 20
nvm use 20

# Navigate to frontend directory
cd frontend

# Initialize Next.js 14 with all options
npx create-next-app@14 . \
  --typescript \
  --tailwind \
  --eslint \
  --app \
  --src-dir \
  --import-alias "@/*"

# Core UI & animation
npm install framer-motion@11.5.4
npm install recharts@2.13.0
npm install @tanstack/react-query@5.56.2
npm install @tanstack/react-query-devtools@5.56.2
npm install axios@1.7.7
npm install lucide-react@0.451.0
npm install clsx@2.1.1
npm install tailwind-merge@2.5.3

# ShadCN UI (install individually as needed)
npx shadcn-ui@latest init
npx shadcn-ui@latest add card badge progress slider tooltip

# D3 for confidence interval visualization
npm install d3@7.9.0
npm install @types/d3@7.4.3
```

### 4.6 Docker Setup

```bash
# Install Docker Desktop (macOS/Windows) or Docker Engine (Linux)
# Verify:
docker --version     # should be 27.x+
docker compose version  # should be 2.x+

# Pull required images
docker pull postgres:16-alpine
docker pull redis:7-alpine
```

### 4.7 Environment Variables

> **v1.1 correction:** Supabase: use the *Session pooler* URI (direct host is IPv6-only). `CELERY_*` URLs may be blank (they default to `REDIS_URL`; `${VAR}` interpolation is not supported). New: `HF_MODEL_REPO`, `MODEL_DIR`, `GEMINI_MODEL`. Canonical list: `.env.example`.

Create `.env` in project root. **Never commit this file.**

```bash
# === DATABASE ===
DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres
SUPABASE_URL=https://[PROJECT_REF].supabase.co
SUPABASE_ANON_KEY=your_anon_key

# === REDIS (Upstash) ===
REDIS_URL=rediss://default:[PASSWORD]@[HOST].upstash.io:6379

# === LABEL GENERATION ===
GEMINI_API_KEY=your_google_ai_studio_key
GROQ_API_KEY=your_groq_key     # fallback

# === HUGGINGFACE ===
HF_TOKEN=your_hf_token         # for private model uploads

# === APP ===
SECRET_KEY=your_random_32_char_secret
ENVIRONMENT=development         # or production
CORS_ORIGINS=http://localhost:3000,https://your-app.vercel.app

# === WORKER ===
CELERY_BROKER_URL=${REDIS_URL}
CELERY_RESULT_BACKEND=${REDIS_URL}
```

---

## 5. Repository Structure

> **v1.1 correction:** Additions: `training/vera_training/` (tested offline package), `backend/app/models/job.py` + migration `002_jobs_outbox.py`, `backend/app/worker/outbox.py`, `backend/app/ml/features.py`, `notebooks/build_notebooks.py`, `render.yaml`, `backend/scripts/start_web_with_worker.sh`. Pages add `/about`; components add `ProductDetail.tsx`.

```
vera/
├── .github/
│   └── workflows/
│       ├── ci.yml              # Run tests on PR
│       └── deploy.yml          # Deploy on main merge
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py             # FastAPI app entry
│   │   ├── config.py           # Settings from .env
│   │   ├── database.py         # SQLAlchemy engine + session
│   │   │
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── reviews.py  # POST /reviews, GET /reviews/{id}
│   │   │   │   ├── products.py # GET /products, GET /products/{id}
│   │   │   │   └── health.py   # GET /health
│   │   │   └── deps.py         # Shared dependencies (DB session etc)
│   │   │
│   │   ├── models/             # SQLAlchemy ORM models
│   │   │   ├── review.py
│   │   │   └── product.py
│   │   │
│   │   ├── schemas/            # Pydantic request/response models
│   │   │   ├── review.py
│   │   │   └── product.py
│   │   │
│   │   ├── ml/                 # The core ML pipeline
│   │   │   ├── pipeline.py     # Orchestrator (calls all agents)
│   │   │   ├── agents/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── preprocessor.py      # Agent 1
│   │   │   │   ├── experience_extractor.py  # Agent 2
│   │   │   │   ├── absa.py              # Agent 3
│   │   │   │   ├── consistency.py       # Agent 4
│   │   │   │   ├── quality.py           # Agent 5
│   │   │   │   ├── domain_rating.py     # Agent 6
│   │   │   │   └── fusion.py            # Agent 7
│   │   │   ├── calibration/
│   │   │   │   ├── conformal.py         # Split conformal prediction
│   │   │   │   └── empirical_bayes.py   # Product-level shrinkage
│   │   │   └── models/                  # Model loaders (ONNX)
│   │   │       ├── loader.py
│   │   │       ├── experience_model.onnx
│   │   │       └── absa_model.onnx
│   │   │
│   │   └── worker/
│   │       ├── celery_app.py   # Celery config
│   │       └── tasks.py        # Async review processing tasks
│   │
│   ├── migrations/             # Alembic migrations
│   │   ├── env.py
│   │   ├── versions/
│   │   │   └── 001_initial.py
│   │   └── alembic.ini
│   │
│   └── tests/
│       ├── test_agents.py
│       ├── test_fusion.py
│       ├── test_calibration.py
│       └── test_api.py
│
├── data/
│   ├── raw/                    # Raw downloads (gitignored, large)
│   ├── processed/              # Cleaned reviews parquet files
│   ├── labels/                 # Gemini-generated labels (2000 rows)
│   │   ├── labels_v1.jsonl
│   │   └── labels_agreement.csv
│   └── models/                 # ONNX model files (gitignored, tracked on HF Hub)
│
├── notebooks/
│   ├── 01_data_exploration.ipynb     # Colab: explore + filter dataset
│   ├── 02_label_generation.ipynb     # Colab: run Gemini labeling
│   ├── 03_agreement_analysis.ipynb   # Colab: measure label quality
│   ├── 04_finetune_experience.ipynb  # Colab: fine-tune DeBERTa (needs GPU)
│   ├── 05_train_fusion.ipynb         # Colab: train XGBoost ensemble
│   ├── 06_calibration.ipynb          # Colab: fit conformal predictor
│   ├── 07_ablation_study.ipynb       # Colab: per-agent ablation
│   └── 08_evaluation_report.ipynb   # Colab: final eval + reporting
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx            # Landing / Review Submit
│   │   │   ├── products/
│   │   │   │   └── page.tsx        # Product Rankings
│   │   │   └── products/[id]/
│   │   │       └── page.tsx        # Product Detail + Reviews
│   │   ├── components/
│   │   │   ├── ScoreCard.tsx       # Corrected score + interval viz
│   │   │   ├── AspectRadar.tsx     # Radar chart for 10 aspects
│   │   │   ├── StarVsCorrect.tsx   # Side-by-side comparison
│   │   │   ├── ReviewForm.tsx      # Review submission form
│   │   │   ├── ProductTable.tsx    # Sortable product rankings
│   │   │   └── ConfidenceBar.tsx   # Interval visualization
│   │   └── lib/
│   │       ├── api.ts              # API client
│   │       └── types.ts            # TypeScript types
│   ├── public/
│   └── package.json
│
├── docker-compose.yml          # Local dev: postgres + redis + backend
├── Dockerfile.backend
├── .env                        # NEVER commit
├── .env.example                # Commit this (with placeholders)
├── PROGRESS.md                 # Claude ↔ Codex handoff tracker
├── HANDOFF.md                  # Latest handoff notes
├── DECISIONS.md                # Architecture decision log
└── README.md
```

---

## 6. Dataset Strategy

### 6.1 Why These Datasets

We need two things: a large unlabeled corpus of real earbud reviews (for training the domain rating model and as the pool for labeling), and pre-trained ABSA capabilities (so we don't need to train from scratch).

We deliberately chose NOT to use existing labeled review datasets as our experience score labels because all of them use star ratings as ground truth — which is exactly what we're trying to replace.

### 6.2 Dataset Inventory (All Verified, All Working)

#### Dataset 1: McAuley-Lab Amazon Reviews 2023 (Base Corpus)

```python
# Load command — verified working
from datasets import load_dataset

# Reviews (text, star, helpful votes, verified purchase)
reviews = load_dataset(
    "McAuley-Lab/Amazon-Reviews-2023",
    "raw_review_Electronics",
    trust_remote_code=True,
    split="full"
)

# Item metadata (title, description, category)
metadata = load_dataset(
    "McAuley-Lab/Amazon-Reviews-2023",
    "raw_meta_Electronics",
    trust_remote_code=True,
    split="full"
)
```

**URL:** https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023

**Fields we use:**
- `rating` → star rating (feature, NOT label)
- `text` → review body (primary input)
- `title` → review title (prepend to text)
- `helpful_vote` → Agent 5 quality signal
- `verified_purchase` → Agent 5 quality signal
- `timestamp` → recency signal
- `parent_asin` → product grouping for cross-validation

**Filtering to earbuds (critical — contamination is real):**

```python
import pandas as pd
from sentence_transformers import SentenceTransformer

EARBUD_KEYWORDS = [
    'earbud', 'earphone', 'in-ear', 'headphone', 'headset',
    'tws', 'wireless ear', 'noise cancel', 'airpod', 'bluetooth ear'
]

def filter_earbuds(df_metadata):
    """Filter products to earbuds/headphones using title keyword match."""
    title_lower = df_metadata['title'].str.lower().fillna('')
    mask = title_lower.str.contains('|'.join(EARBUD_KEYWORDS), regex=True)
    return df_metadata[mask]['parent_asin'].unique()

# Apply: get valid earbud ASINs, then filter reviews
earbud_asins = filter_earbuds(metadata_df)
earbud_reviews = reviews_df[reviews_df['parent_asin'].isin(earbud_asins)]

# Further filter: only reviews with 20+ words (meaningful text)
earbud_reviews = earbud_reviews[
    earbud_reviews['text'].str.split().str.len() >= 20
]

print(f"Filtered to {len(earbud_reviews):,} earbud reviews")
# Expected: ~144,000 reviews across ~26,000 products
```

---

#### Dataset 2: yangheng/deberta-v3-base-absa-v1.1 (ABSA Model)

This is a model, not a dataset — but it eliminates the need for ABSA training data entirely. Already trained on **180,000+ examples** from SemEval-2014, SemEval-2016, MAMS, and more. We use it directly in Agent 3.

```python
# Agent 3 initialization — no fine-tuning needed
from pyabsa import AspectSentimentTripletExtraction as ASTE
from pyabsa import ModelSavePath

# Load the pre-trained model
aspect_extractor = ASTE.AspectExtractor('multilingual', auto_device=True)
```

**URL:** https://huggingface.co/yangheng/deberta-v3-base-absa-v1.1

---

#### Dataset 3: tomaarsen/setfit-absa-semeval-laptops (ABSA Benchmark)

We use this for **out-of-domain validation only** — to verify our ABSA agent works on held-out electronics reviews it has never seen in production format.

```python
# Cross-domain validation only, NOT for training
absa_benchmark = load_dataset("tomaarsen/setfit-absa-semeval-laptops")
# Fields: sentence, aspect, label (positive/negative/neutral)
```

**URL:** https://huggingface.co/datasets/tomaarsen/setfit-absa-semeval-laptops

---

#### Dataset 4: Our Gemini-Generated Labels (2000 reviews)

The labels WE generate, from scratch, using Gemini 1.5 Flash. Experience score 1–5 derived purely from text. See §7 for full protocol. Saved to `data/labels/labels_v1.jsonl`.

---

### 6.3 Sampling Strategy for Labeling Pool

> **v1.1 correction:** The per-product cap is enforced GLOBALLY across star buckets (the sketch capped per bucket, allowing 25 reviews/product). Implementation: `vera_training.data.sample_for_labeling`.

We need 2,000 labels but have 144,000 reviews. How we sample matters a lot for class imbalance and model generalization:

```python
import numpy as np
from sklearn.model_selection import StratifiedShuffleSplit

def sample_for_labeling(reviews_df, n=2000, seed=42):
    """
    Stratified sample:
    - 20% per star rating bucket (400 each, 5 buckets = 2000)
    - Within each bucket: prefer high helpful_vote reviews (they're more trustworthy)
    - Within each bucket: ensure product diversity (no product > 5 reviews)
    """
    np.random.seed(seed)
    selected = []
    
    for star in [1, 2, 3, 4, 5]:
        bucket = reviews_df[reviews_df['rating'] == float(star)].copy()
        
        # Soft sort: high helpful votes first (diversity through sampling)
        bucket['weight'] = np.log1p(bucket['helpful_vote']) + 0.1
        bucket['weight'] /= bucket['weight'].sum()
        
        # Cap per-product to 5 reviews
        product_counts = bucket.groupby('parent_asin').cumcount()
        bucket = bucket[product_counts < 5]
        
        n_bucket = min(400, len(bucket))
        sampled = bucket.sample(n=n_bucket, weights='weight', random_state=seed)
        selected.append(sampled)
    
    return pd.concat(selected).sample(frac=1, random_state=seed).reset_index(drop=True)

labeling_pool = sample_for_labeling(earbud_reviews_df)
```

**Result:** 400 reviews × 5 star ratings = 2,000 reviews. Equal representation prevents the 54.7% five-star skew from contaminating our training labels.

---

## 7. Labeling Protocol — Gemini Flash

### 7.1 Labeler Selection and Validation

> **v1.2 correction:** The current labeling configuration uses Groq-hosted
> `openai/gpt-oss-120b` and `qwen/qwen3.8-27b`; Gemini is legacy support, not the active
> provider. Claude's annotations are a non-human reference only. No human-model agreement
> result may be claimed until human annotations are actually collected. (§23 #22, #27)

Label reliability is assessed with independent repeat runs and reference agreement. Agreement with
an LLM reference is reported as reference-model agreement, not human validation. The G1 thresholds
remain unchanged; the human-model criterion in §22.1 stays unmet until genuine human annotations
are collected.

### 7.2 The Labeling Prompt (Exact, No Changes)

```python
SYSTEM_PROMPT = """You are an expert product experience analyst. 
Your job is to read product reviews and estimate the actual customer experience — 
completely ignoring the star rating they gave.

Stars are unreliable. Focus ONLY on what the text says about the experience.
Return ONLY valid JSON. No markdown, no explanation, no preamble."""

USER_PROMPT_TEMPLATE = """Product: {product_title}

Review text:
\"\"\"
{review_text}
\"\"\"

Return a JSON object with this exact schema:
{{
  "experience_score": <float, one of [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]>,
  "experience_rationale": "<one sentence: what specific evidence led to this score>",
  "has_irony_or_sarcasm": <true or false>,
  "review_quality": "<one of: low, medium, high>",
  "aspects": {{
    "sound_quality":      {{"mentioned": <bool>, "sentiment": "<positive|negative|neutral|not_mentioned>"}},
    "bass":               {{"mentioned": <bool>, "sentiment": "<positive|negative|neutral|not_mentioned>"}},
    "battery_life":       {{"mentioned": <bool>, "sentiment": "<positive|negative|neutral|not_mentioned>"}},
    "comfort":            {{"mentioned": <bool>, "sentiment": "<positive|negative|neutral|not_mentioned>"}},
    "fit":                {{"mentioned": <bool>, "sentiment": "<positive|negative|neutral|not_mentioned>"}},
    "build_quality":      {{"mentioned": <bool>, "sentiment": "<positive|negative|neutral|not_mentioned>"}},
    "connectivity":       {{"mentioned": <bool>, "sentiment": "<positive|negative|neutral|not_mentioned>"}},
    "microphone":         {{"mentioned": <bool>, "sentiment": "<positive|negative|neutral|not_mentioned>"}},
    "noise_cancellation": {{"mentioned": <bool>, "sentiment": "<positive|negative|neutral|not_mentioned>"}},
    "value":              {{"mentioned": <bool>, "sentiment": "<positive|negative|neutral|not_mentioned>"}}
  }}
}}"""
```

### 7.3 Labeling Script

> **v1.1 correction:** Use `vera_training.labeling.run_labels`: star-blinded, strict schema validation, hard request budget, atomic resumable checkpoints (the sketch overwrote its checkpoint every 100 rows and never saved the final batch).

```python
# notebooks/02_label_generation.ipynb

import google.generativeai as genai
import json, time
from pathlib import Path

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-flash')

generation_config = genai.GenerationConfig(
    response_mime_type="application/json",   # structured JSON output
    temperature=0.1,                          # low temp = consistent labels
    max_output_tokens=1024,
)

def label_review(review_text, product_title, max_retries=3):
    prompt = USER_PROMPT_TEMPLATE.format(
        product_title=product_title[:200],
        review_text=review_text[:1500],      # cap at 1500 chars
    )
    for attempt in range(max_retries):
        try:
            response = model.generate_content(
                [SYSTEM_PROMPT, prompt],
                generation_config=generation_config
            )
            label = json.loads(response.text)
            # Validate schema
            assert 'experience_score' in label
            assert label['experience_score'] in [1.0,1.5,2.0,2.5,3.0,3.5,4.0,4.5,5.0]
            return label
        except Exception as e:
            if attempt == max_retries - 1:
                return None  # mark for re-labeling
            time.sleep(2 ** attempt)  # exponential backoff

# Run with rate limiting (stay within 1M token/day)
labels = []
for i, row in labeling_pool.iterrows():
    label = label_review(row['text'], row.get('product_title', ''))
    if label:
        label['review_id'] = row.name
        label['star_rating'] = row['rating']
        labels.append(label)
    
    if i % 100 == 0:
        # Save checkpoint
        Path('data/labels/labels_checkpoint.jsonl').write_text(
            '\n'.join(json.dumps(l) for l in labels)
        )
        print(f"Labeled {i}/{len(labeling_pool)} reviews")
    
    time.sleep(0.5)  # 2 req/sec to stay safe
```

### 7.4 Agreement Measurement (Critical for Academic Validity)

```python
# notebooks/03_agreement_analysis.ipynb

from sklearn.metrics import cohen_kappa_score
import numpy as np

# Step 1: Self-consistency check — label same 200 reviews twice
def measure_self_consistency(sample_200, n_rounds=2):
    """Label same reviews twice with different model seeds."""
    all_labels = []
    for round_i in range(n_rounds):
        round_labels = []
        for _, row in sample_200.iterrows():
            label = label_review(row['text'], row.get('product_title', ''))
            round_labels.append(label['experience_score'] if label else None)
        all_labels.append(round_labels)
    
    valid = [(r1, r2) for r1, r2 in zip(all_labels[0], all_labels[1]) 
             if r1 is not None and r2 is not None]
    r1_vals = [v[0] for v in valid]
    r2_vals = [v[1] for v in valid]
    
    # Quadratic kappa (treats 1-vs-5 worse than 4-vs-5)
    kappa = cohen_kappa_score(
        [round(v * 2) for v in r1_vals],   # convert to int (×2 for 0.5 steps)
        [round(v * 2) for v in r2_vals],
        weights='quadratic'
    )
    mae = np.mean(np.abs(np.array(r1_vals) - np.array(r2_vals)))
    return kappa, mae

kappa, mae = measure_self_consistency(labeling_pool.head(200))
print(f"Self-consistency kappa: {kappa:.3f}, MAE: {mae:.3f}")
# Target: kappa > 0.70, MAE < 0.40
# If below target: tighten prompt, add few-shot examples

# Step 2: Human validation on 200 reviews
# You manually label 200 reviews → compute human-Gemini kappa
# human_labels: list of 200 scores (your ground truth)
def measure_human_agreement(human_labels, gemini_labels):
    kappa = cohen_kappa_score(
        [round(v * 2) for v in human_labels],
        [round(v * 2) for v in gemini_labels],
        weights='quadratic'
    )
    return kappa
```

**Target agreement metrics:**

| Metric | Minimum to Proceed | What to Do if Below |
|---|---|---|
| Self-consistency kappa | > 0.70 | Add few-shot examples to prompt |
| Human-Gemini kappa | > 0.55 | Add chain-of-thought to prompt |
| Human-Gemini MAE | < 0.60 | Filter out irony/sarcasm reviews before labeling |

---

## 8. System Architecture

### 8.1 High-Level Overview

```mermaid
flowchart TD
    USER([User / Browser]) -->|Submit review| FE[Next.js 14\nFrontend — Vercel]
    FE -->|POST /api/reviews| API[FastAPI\nBackend — Render]
    API -->|Enqueue task| RQ[(Upstash Redis\nTask Queue)]
    RQ -->|Dequeue| WK[Celery Worker\nRender Background]
    WK -->|Run pipeline| ML[7-Agent ML Pipeline]
    ML -->|Store result| DB[(Supabase\nPostgreSQL)]
    DB -->|Poll / Webhook| API
    API -->|JSON result| FE
    FE -->|Render score| USER

    style FE fill:#1a1a2e,stroke:#7C3AED,color:#e2e8f0
    style API fill:#1a1a2e,stroke:#00B4D8,color:#e2e8f0
    style WK fill:#1a1a2e,stroke:#00B4D8,color:#e2e8f0
    style ML fill:#16213E,stroke:#10B981,color:#e2e8f0
    style DB fill:#1a1a2e,stroke:#F59E0B,color:#e2e8f0
    style RQ fill:#1a1a2e,stroke:#F59E0B,color:#e2e8f0
```

### 8.2 ML Pipeline (Detailed Agent Flow)

```mermaid
flowchart TD
    IN([Review Input\ntext + star + metadata]) --> A1

    subgraph PIPELINE ["7-Agent Signal Extraction Pipeline"]
        A1[Agent 1\nText Preprocessor]
        A2[Agent 2\nExperience Extractor]
        A3[Agent 3\nABSA Module]
        A4[Agent 4\nConsistency Scorer]
        A5[Agent 5\nReview Quality]
        A6[Agent 6\nDomain Rating]
        A7[Agent 7\nFusion + Calibration]

        A1 -->|clean text + quality flags| A2
        A1 -->|clean text| A3
        A1 -->|clean text| A4
        IN -->|star + metadata| A4
        IN -->|metadata| A5
        A1 -->|clean text| A6
        A2 -->|experience dist| A7
        A3 -->|aspect sentiment| A7
        A4 -->|consistency score| A7
        A5 -->|quality score| A7
        A6 -->|domain rating| A7
    end

    A7 --> CONF[Conformal\nCalibration]
    CONF --> EB[Empirical Bayes\nProduct Aggregation]
    EB --> OUT([Final Output\nscore + interval + aspects])

    style PIPELINE fill:#0A0A0F,stroke:#7C3AED,color:#e2e8f0
    style CONF fill:#16213E,stroke:#10B981,color:#e2e8f0
    style EB fill:#16213E,stroke:#10B981,color:#e2e8f0
```

### 8.3 Data Pipeline (Offline, One-Time Setup)

```mermaid
flowchart LR
    RAW[McAuley-Lab\nAmazon Reviews 2023] --> FILT[Keyword + Embedding\nContamination Filter]
    FILT --> POOL[144K Earbud Reviews\nLabeling Pool]
    POOL --> STRAT[Stratified Sample\n2000 reviews — 400/star]
    STRAT --> GEMINI[Gemini Flash\nLabeling API]
    GEMINI --> VALID{Agreement\nCheck}
    VALID -->|kappa < 0.70| REFINE[Refine Prompt\n+ Few-shot]
    REFINE --> GEMINI
    VALID -->|kappa ≥ 0.70| LABELS[(2000 Labels\nlabels_v1.jsonl)]
    LABELS --> SPLIT[Product-grouped\nTrain/Val/Test Split]
    SPLIT --> FT[Fine-tune DeBERTa\non Colab T4]
    FT --> ONNX[Export ONNX INT8\n~90MB]
    ONNX --> HFH[HuggingFace Hub\nModel Storage]
    HFH --> PROD[Production\nInference]
```

### 8.4 Deployment Architecture

```mermaid
flowchart TD
    subgraph VERCEL ["Vercel (Frontend)"]
        FE[Next.js 14\nSSR + Static]
    end

    subgraph RENDER ["Render (Backend)"]
        API[FastAPI\nWeb Service\n512MB RAM]
        WK1[Celery Worker 1\nBackground Worker]
        WK2[Celery Worker 2\nBackground Worker]
    end

    subgraph SUPABASE ["Supabase (Database)"]
        PG[(PostgreSQL 16\n500MB free)]
    end

    subgraph UPSTASH ["Upstash (Cache)"]
        RD[(Redis 7\n10K cmds/day)]
    end

    subgraph HF ["HuggingFace Hub"]
        MDL[ONNX Models\nexperience + absa]
    end

    subgraph UPTIMEROBOT ["UptimeRobot"]
        PING[Ping every 5min\nPrevents cold start]
    end

    FE <-->|HTTPS| API
    API <-->|SQLAlchemy| PG
    API <-->|Redis protocol| RD
    WK1 <-->|Celery| RD
    WK2 <-->|Celery| RD
    WK1 <-->|SQLAlchemy| PG
    WK2 <-->|SQLAlchemy| PG
    API -->|Pull at startup| MDL
    PING -->|GET /health| API
```

---

## 9. Agent Specifications

### Agent 1: Text Preprocessor

> **v1.1 correction:** `has_url` is computed on RAW text (it was always False after URL stripping); `<br/>` becomes a space; keywords match on word boundaries. (§23 #6)

**Purpose:** Gate all downstream agents with clean, validated input. Detect contamination (non-earbud products), language, and compute text quality metrics that inform later agents.

**Why it's first:** Garbage in → garbage out. Every downstream signal depends on clean text. Contamination detection here prevents non-earbud products from polluting our scores.

**Inputs:** Raw review text, product title
**Outputs:** `{clean_text, is_earbud, language, word_count, vocab_richness, avg_sentence_length, has_code_or_url}`

```python
# backend/app/ml/agents/preprocessor.py
#
# DESIGN CONSTRAINT: Agent 1 must have ZERO torch / transformers imports.
# Loading SentenceTransformer (PyTorch) here would add ~350MB RAM on top of
# the two ONNX models (Agents 2 & 3), blowing past Render's 512MB ceiling.
# Instead we use:
#   - langdetect (pure Python, ~1 MB) for language detection
#   - sklearn TF-IDF cosine (reuses the domain-model vocabulary, no new model)
#   - keyword matching for title (high precision, zero cost)

import re
import numpy as np
from langdetect import detect, DetectorFactory
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DetectorFactory.seed = 42   # make langdetect deterministic

class TextPreprocessor:
    """
    Agent 1: Clean, validate, and characterize review text.
    Pure numpy + sklearn — no PyTorch, no SentenceTransformers, no FastText.
    """
    EARBUD_KEYWORDS = [
        'earbud', 'earphone', 'in-ear', 'headphone', 'headset',
        'tws', 'true wireless', 'noise cancel', 'airpod',
        'bluetooth ear', 'over-ear', 'on-ear', 'anc', 'wireless ear'
    ]

    # Anchor phrases for TF-IDF cosine fallback (no model download needed)
    _ANCHORS = [
        "sound quality is great", "bass is powerful", "noise cancellation works",
        "battery life lasts hours", "fit in my ear comfortably", "earbud fell out",
        "earphone sounds", "in-ear headphone", "bluetooth connection drops",
        "microphone quality for calls", "charging case", "pairing device",
    ]

    def __init__(self):
        # Fit a tiny TF-IDF on the anchor phrases once at startup.
        # This adds ~1 MB to RAM — negligible.
        self._vec = TfidfVectorizer(ngram_range=(1, 2), max_features=2000)
        self._vec.fit(self._ANCHORS)
        self._anchor_matrix = self._vec.transform(self._ANCHORS)  # (12, vocab)

    # ------------------------------------------------------------------
    def clean_text(self, text: str) -> str:
        text = re.sub(r'http\S+', '', text)       # strip URLs
        text = re.sub(r'<[^>]+>', '', text)        # strip HTML tags
        text = re.sub(r'\s+', ' ', text).strip()  # normalise whitespace
        return text

    def detect_language(self, text: str) -> str:
        # langdetect throws LangDetectException on texts shorter than ~10
        # characters, emoji-heavy inputs, or strings containing only
        # punctuation.  These are not retryable errors — they are expected
        # edge cases in user-submitted reviews.  We fail-open to 'en'
        # because (a) our corpus is English-only and (b) the primary job
        # here is to REJECT non-English reviews, not to distinguish 176
        # languages.  A review that we can't classify will be processed and
        # the quality assessor will naturally score it low if it is gibberish.
        try:
            cleaned = text.strip()
            if len(cleaned) < 10:
                return 'en'          # too short to detect — assume English
            return detect(cleaned[:500])
        except Exception:
            return 'en'              # fail-open; never let this crash the task

    def is_earbud_content(self, text: str, title: str) -> tuple[bool, float]:
        """
        Two-stage contamination filter — no torch required.

        Stage 1 — keyword match on title + first 200 chars of body (O(1)).
            High precision: if the title says "earbud" we trust it.
        Stage 2 — TF-IDF cosine on body text against earbud anchor phrases.
            Catches reviews whose *title* is absent / generic but whose body
            is clearly about audio hardware.
        """
        # Stage 1: fast keyword scan
        combined = f"{title or ''} {text[:200]}".lower()
        if any(kw in combined for kw in self.EARBUD_KEYWORDS):
            return True, 1.0

        # Stage 2: lightweight TF-IDF cosine (sklearn, ~0 ms)
        text_vec = self._vec.transform([text[:500]])
        sims = cosine_similarity(text_vec, self._anchor_matrix)[0]
        max_sim = float(sims.max())
        return max_sim > 0.25, max_sim

    def quality_metrics(self, text: str) -> dict:
        words = text.split()
        sentences = [s.strip() for s in re.split(r'[.!?]+', text) if len(s.strip()) > 3]
        unique_words = set(w.lower() for w in words)
        return {
            'word_count': len(words),
            'sentence_count': max(len(sentences), 1),
            'avg_sentence_length': len(words) / max(len(sentences), 1),
            'vocab_richness': len(unique_words) / max(len(words), 1),
            'has_url': bool(re.search(r'http', text)),
        }

    def process(self, text: str, title: str = '') -> dict:
        clean = self.clean_text(text)
        lang = self.detect_language(clean)
        is_earbud, earbud_score = self.is_earbud_content(clean, title)
        metrics = self.quality_metrics(clean)
        return {
            'clean_text': clean,
            'language': lang,
            'is_english': lang == 'en',
            'is_earbud': is_earbud,
            'earbud_confidence': earbud_score,
            **metrics,
        }
```

---

### Agent 2: Experience Extractor

> **v1.1 correction:** No `transformers` import in production; inference and training both use `format_experience_input(clean_text)` (the sketch prepended the title only at inference). ONNX feeds only declared inputs (no `token_type_ids` for DeBERTa-v3). (§23 #4, #7)

**Purpose:** Estimate the actual experience score from text alone. This is our primary model — fine-tuned DeBERTa-v3-base with a regression head, trained on our 2000 Gemini-labeled reviews.

**Why DeBERTa-v3-base:** Disentangled attention mechanism captures both content and position independently, outperforming BERT and RoBERTa on sentiment tasks. Base size (184M params) fits in memory after ONNX quantization.

**Why regression, not classification:** Experience score is ordinal (1 < 2 < 3 < 4 < 5) with meaningful distances. Regression respects this ordering; 5-class classification treats 1 and 5 as equally "wrong" from 3.

**Inputs:** `clean_text` from Agent 1
**Outputs:** `{predicted_score, score_distribution, model_uncertainty}`

```python
# backend/app/ml/agents/experience_extractor.py

import onnxruntime as ort
import numpy as np
from transformers import AutoTokenizer

class ExperienceExtractor:
    """
    Agent 2: Fine-tuned DeBERTa-v3-base → experience score.
    Runs ONNX INT8 quantized for CPU speed (~90ms per inference).
    """
    
    def __init__(self, model_path: str = 'data/models/experience_model.onnx'):
        self.tokenizer = AutoTokenizer.from_pretrained('microsoft/deberta-v3-base')
        
        # ONNX Runtime session with CPU optimizations
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 2
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = ort.InferenceSession(model_path, sess_options=opts)
    
    def predict(self, text: str, title: str = '') -> dict:
        # Prepend title for context if available
        input_text = f"{title} [SEP] {text}" if title else text
        
        # Tokenize
        encoded = self.tokenizer(
            input_text,
            max_length=512,
            truncation=True,
            padding='max_length',
            return_tensors='np'
        )
        
        # Run ONNX inference
        outputs = self.session.run(None, {
            'input_ids': encoded['input_ids'].astype(np.int64),
            'attention_mask': encoded['attention_mask'].astype(np.int64),
            'token_type_ids': encoded.get('token_type_ids', 
                np.zeros_like(encoded['input_ids'])).astype(np.int64),
        })
        
        # Output: [batch, 1] regression score
        raw_score = float(outputs[0][0][0])
        
        # Clip to valid range
        predicted_score = float(np.clip(raw_score, 1.0, 5.0))
        
        # Uncertainty proxy: distance from 0.5-step boundary
        nearest_half = round(raw_score * 2) / 2
        model_uncertainty = abs(raw_score - nearest_half)
        
        return {
            'predicted_score': predicted_score,
            'raw_score': raw_score,
            'model_uncertainty': model_uncertainty,
        }
```

---

### Agent 3: ABSA Module

> **v1.1 correction:** Single batched ONNX call; numerically stable softmax; label map from exported `absa_config.json`; aspect keys are snake_case (`sound_quality`) everywhere. (§23 #8)

**Purpose:** Detect which of the 10 earbud aspects are mentioned and classify sentiment for each. Uses the pre-trained `yangheng/deberta-v3-base-absa-v1.1` (180K training examples) directly — no fine-tuning needed.

**Why pre-trained, not fine-tuned:** The pre-trained model already knows electronics sentiment. Our 2000 labels don't have enough aspect-level signal to reliably fine-tune on top of it. We get better results using it as-is.

**Inputs:** `clean_text` from Agent 1
**Outputs:** `{aspects: {aspect_name: {detected, sentiment, confidence}}}`

```python
# backend/app/ml/agents/absa.py

import onnxruntime as ort
import numpy as np
from transformers import AutoTokenizer

EARBUD_ASPECTS = [
    'sound quality', 'bass', 'battery life', 'comfort', 'fit',
    'build quality', 'connectivity', 'microphone', 'noise cancellation', 'value'
]

ASPECT_KEYWORDS = {
    'sound quality': ['sound','audio','music','clarity','treble','highs','mids'],
    'bass':          ['bass','low end','boom','thump','sub'],
    'battery life':  ['battery','charge','hours','playtime','charging','endurance'],
    'comfort':       ['comfort','comfortable','ear pain','hurt','wear'],
    'fit':           ['fit','stay in','fall out','tip','seal','ear tip'],
    'build quality': ['build','quality','cheap','durable','plastic','sturdy','broke'],
    'connectivity':  ['bluetooth','connect','disconnect','pair','latency','range','signal'],
    'microphone':    ['mic','microphone','call','voice','recording'],
    'noise cancellation': ['anc','noise cancel','passive','block','isolat'],
    'value':         ['price','value','worth','money','cheap','expensive','cost'],
}

class ABSAModule:
    """
    Agent 3: Aspect-Based Sentiment Analysis.
    Uses yangheng/deberta-v3-base-absa-v1.1 (ONNX quantized).
    Falls back to keyword detection for implicit mentions.
    """
    SENTIMENT_MAP = {0: 'negative', 1: 'neutral', 2: 'positive'}
    
    def __init__(self, model_path: str = 'data/models/absa_model.onnx'):
        self.tokenizer = AutoTokenizer.from_pretrained(
            'yangheng/deberta-v3-base-absa-v1.1'
        )
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 2
        self.session = ort.InferenceSession(model_path, sess_options=opts)
    
    def classify_aspect_sentiment(self, text: str, aspect: str) -> dict:
        """Run ABSA model for one (text, aspect) pair.

        Argument order matters: yangheng/deberta-v3-base-absa-v1.1 expects
        the review body as the *first* sentence and the aspect as the
        *second* sentence, matching the PyABSA training format
        [CLS] review_text [SEP] aspect [SEP].
        Passing (aspect, text) truncates review context first — wrong.
        max_length raised to 512 so long reviews are not silently cut.
        """
        encoded = self.tokenizer(
            text, aspect,        # ← text FIRST, aspect SECOND
            max_length=512,      # ← was 256; ensure full review context
            truncation=True,
            padding='max_length',
            return_tensors='np'
        )
        
        outputs = self.session.run(None, {
            'input_ids': encoded['input_ids'].astype(np.int64),
            'attention_mask': encoded['attention_mask'].astype(np.int64),
        })
        
        # Output: [batch, 3] logits (neg/neu/pos)
        logits = outputs[0][0]
        probs = np.exp(logits) / np.exp(logits).sum()
        pred_idx = int(np.argmax(probs))
        
        return {
            'sentiment': self.SENTIMENT_MAP[pred_idx],
            'confidence': float(probs[pred_idx]),
            'prob_neg': float(probs[0]),
            'prob_neu': float(probs[1]),
            'prob_pos': float(probs[2]),
        }
    
    def keyword_detect(self, text: str, aspect: str) -> bool:
        """Fast keyword pre-filter: skip ONNX call if aspect not mentioned."""
        text_lower = text.lower()
        return any(kw in text_lower for kw in ASPECT_KEYWORDS[aspect])
    
    def process(self, text: str) -> dict:
        results = {}
        for aspect in EARBUD_ASPECTS:
            # First check keywords (fast)
            detected = self.keyword_detect(text, aspect)
            
            if detected:
                # Run full ABSA model only if aspect is likely mentioned
                sent_result = self.classify_aspect_sentiment(text, aspect)
                results[aspect] = {
                    'detected': True,
                    **sent_result
                }
            else:
                results[aspect] = {
                    'detected': False,
                    'sentiment': 'not_mentioned',
                    'confidence': 0.0,
                }
        
        return {'aspects': results}
```

---

### Agent 4: Star-Text Consistency Scorer

**Purpose:** Measure how much the star rating disagrees with the text. High divergence means the star should be downweighted in fusion and is itself a strong signal of label noise.

**Inputs:** Star rating, Agent 2's experience score
**Outputs:** `{gap, absolute_gap, star_inflated, star_deflated, consistency_score}`

```python
# backend/app/ml/agents/consistency.py

class ConsistencyScorer:
    """
    Agent 4: Measure gap between star and text-derived experience score.
    A large gap = star is unreliable = text carries more weight in fusion.
    """
    
    def process(self, star_rating: float, experience_score: float) -> dict:
        gap = star_rating - experience_score       # positive = star > text
        abs_gap = abs(gap)
        
        # Consistency score: 1.0 = perfect agreement, 0.0 = maximum disagreement
        # Max possible gap is 4 (1 vs 5)
        consistency_score = 1.0 - (abs_gap / 4.0)
        
        return {
            'star_text_gap': round(gap, 3),
            'absolute_gap': round(abs_gap, 3),
            'star_inflated': gap > 1.0,       # reviewer clicked higher than text implies
            'star_deflated': gap < -1.0,      # reviewer clicked lower than text implies
            'consistency_score': round(consistency_score, 3),
            'star_trust_weight': consistency_score ** 2,  # downweight stars more aggressively
        }
```

---

### Agent 5: Review Quality Assessor

> **v1.1 correction:** Composite is a plain weighted average (the sketch referenced `quality_score` in its own definition); freshness uses a true half-life `0.5**(age/730)` clipped at age 0; missing metadata imputed from training means in the fusion artifact. (§23 #9)

**Purpose:** Estimate how trustworthy this review is as a signal. High-quality reviews get more weight in the product aggregation step.

**Inputs:** Metadata (helpful_votes, verified_purchase, timestamp, word_count)
**Outputs:** `{quality_score, helpfulness_score, freshness_score, trust_weight}`

```python
# backend/app/ml/agents/quality.py

import numpy as np
from datetime import datetime

class QualityAssessor:
    """
    Agent 5: Score review trustworthiness from metadata signals.
    These are interpretable heuristics, not a learned model.
    """
    CUTOFF_DATE = datetime(2023, 9, 1)  # dataset end date
    
    def process(self, helpful_votes: int, verified: bool,
                timestamp: int, word_count: int) -> dict:
        
        # Helpfulness: log-normalized (diminishing returns)
        helpfulness = np.log1p(helpful_votes) / np.log1p(100)  # normalize at 100 votes
        helpfulness = float(np.clip(helpfulness, 0, 1))
        
        # Freshness: reviews from last 2 years are more relevant
        review_date = datetime.fromtimestamp(timestamp / 1000)
        age_days = (self.CUTOFF_DATE - review_date).days
        freshness = float(np.exp(-age_days / 730))  # 2-year half-life
        
        # Length score: longer reviews are more informative (up to 500 words)
        length_score = float(np.clip(word_count / 500, 0, 1))
        
        # Verified purchase adds hard credibility
        verified_bonus = 0.15 if verified else 0.0
        
        # Composite quality score (weighted average)
        quality_score = (
            0.35 * helpfulness +
            0.25 * freshness +
            0.25 * length_score +
            0.15 * (1.0 if verified else 0.0)
        ) + verified_bonus * (1 - quality_score if 'quality_score' in dir() else 0)
        
        quality_score = float(np.clip(quality_score, 0.05, 1.0))
        
        return {
            'helpfulness_score': round(helpfulness, 3),
            'freshness_score': round(freshness, 3),
            'length_score': round(length_score, 3),
            'verified_purchase': verified,
            'quality_score': round(quality_score, 3),
            'trust_weight': round(quality_score, 3),  # used in product aggregation
        }
```

---

### Agent 6: Domain Rating Model

> **v1.1 correction:** Training lives in `vera_training.domain.train_domain_model`; excludes ALL labelled ASINs; drops `stop_words_`; artifact `domain_tfidf.joblib` records sklearn/numpy versions and must be trained in the production-pinned env. (§23 #19)

**Purpose:** A TF-IDF model trained on ALL 144K unlabeled earbud reviews that predicts an implied rating from text alone — without ever seeing the star. This captures domain-specific vocabulary patterns (e.g., "tinny" always correlates with low experience scores in our domain).

**Why this matters:** This agent provides signal completely orthogonal to the star rating — it learned purely from text patterns in the unlabeled corpus. It's our weakest individual signal but consistently adds value in the ensemble.

**Inputs:** `clean_text` from Agent 1
**Outputs:** `{domain_score, domain_confidence}`

```python
# backend/app/ml/agents/domain_rating.py

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge

class DomainRatingModel:
    """
    Agent 6: TF-IDF → Ridge regression trained on UNLABELED corpus.
    Uses star ratings from unlabeled data as a NOISY proxy signal
    (only for this agent — these noisy labels are acceptable here
    because we're learning text patterns, not predicting ground truth).
    """
    
    @classmethod
    def train(cls, unlabeled_df, held_out_asins: set,
              model_path='data/models/domain_tfidf.pkl'):
        """One-time training on the unlabeled corpus.

        LEAKAGE GUARD: `held_out_asins` must contain every product ASIN
        that appears in the labelled test split.  We exclude those rows
        *before* fitting the TF-IDF vocabulary and Ridge coefficients.
        If we skip this step, the vocabulary learns from test reviews and
        inflates cross-validation scores on the domain-rating feature.

        Usage:
            test_asins = set(test_df['parent_asin'].unique())
            DomainRatingModel.train(unlabeled_df, held_out_asins=test_asins)
        """
        safe_df = unlabeled_df[~unlabeled_df['parent_asin'].isin(held_out_asins)]
        print(f"Domain model: {len(safe_df):,} rows after excluding "
              f"{len(unlabeled_df) - len(safe_df):,} held-out-ASIN rows")

        vectorizer = TfidfVectorizer(
            max_features=50_000,
            ngram_range=(1, 2),   # unigrams + bigrams
            min_df=5,             # must appear in 5+ reviews
            max_df=0.95,          # ignore ultra-common terms
            sublinear_tf=True,    # log scaling
        )
        
        X = vectorizer.fit_transform(safe_df['text'])
        y = safe_df['rating'].values.astype(float)
        
        model = Ridge(alpha=10.0)
        model.fit(X, y)
        
        joblib.dump({'vectorizer': vectorizer, 'model': model}, model_path)
        print(f"Domain model trained. Train R²: {model.score(X, y):.3f}")
        return cls(model_path)
    
    def __init__(self, model_path='data/models/domain_tfidf.pkl'):
        artifacts = joblib.load(model_path)
        self.vectorizer = artifacts['vectorizer']
        self.model = artifacts['model']
    
    def process(self, text: str) -> dict:
        X = self.vectorizer.transform([text])
        raw_score = float(self.model.predict(X)[0])
        domain_score = float(np.clip(raw_score, 1.0, 5.0))
        
        # Confidence: residual variance proxy (Ridge doesn't give uncertainty natively)
        # Use distance from integer boundary as uncertainty estimate
        domain_confidence = 1.0 - abs(domain_score - round(domain_score))
        
        return {
            'domain_score': round(domain_score, 3),
            'domain_confidence': round(domain_confidence, 3),
        }
```

---

### Agent 7: Fusion + Calibration

See §10 for full details. This agent takes all signals from Agents 1–6 and produces the final corrected score + confidence interval.

---

## 10. Fusion & Calibration Layer

### 10.1 Feature Engineering

> **v1.1 correction:** The 40-feature contract lives in `backend/app/ml/features.py` and is shared by training and serving. Imputation happens inside Agent 5 (the sketch's `imputation` argument was never used). Training uses 50% metadata dropout; calibration/test use 100% to match API inputs. (§23 #10, #18)

**Feature shift problem and mitigation.**
API users submit reviews without `helpful_votes` or `verified_purchase` — those fields are optional in `ReviewCreate` and default to `0` / `False`.  If your XGBoost model was trained exclusively on high-quality, heavily-voted reviews (e.g. because you over-sampled them for labelling), the `quality_score` and `helpfulness_score` features will be systematically smaller in production than in training.  When conformal calibration is fitted on training-distribution features but production inputs carry different feature distributions, intervals widen or narrow incorrectly.

**Three-part fix applied:**

1. **Training covers zero-metadata reviews.** Notebook 05 trains on the full labelled set, which already includes many reviews with `helpful_votes = 0` and `verified_purchase = False` (most Amazon reviews have zero helpful votes).  Do NOT filter these out before training.

2. **Production uses the training-mean imputation, not hard zeros.** When a field is absent, fill it with the training-set mean, not 0. Store the training means alongside the XGBoost model pickle and apply them at prediction time.

3. **Calibration set mirrors production distribution.** The conformal calibration set (20% product-grouped hold-out) must include zero-metadata reviews in the same proportions as the full labelled set. Do NOT calibrate on a subset that was filtered for helpfulness or verification status.

```python
# backend/app/ml/agents/fusion.py  (feature construction with imputation)

# ── Imputation constants (computed once in notebook 05, stored in model pickle) ──
# These are dataset-level means from the 2000-review labelled set.
# Load them from disk — never hardcode them, as they shift with new label runs.
IMPUTATION_DEFAULTS = {
    'helpful_votes':    0.0,    # recomputed from training set in notebook 05
    'quality_score':    0.45,   # training-set mean quality score
    'freshness_score':  0.60,   # training-set mean freshness
    'length_score':     0.42,   # training-set mean length score
}

def build_feature_vector(agent_outputs: dict, imputation: dict = None) -> np.ndarray:
    """
    Build the ~40-feature vector for XGBoost inference.

    `imputation` contains training-set means for optional metadata fields.
    When a field is missing from the API request, use the training mean —
    NOT zero — so production feature distributions match the calibration set.
    """
    imp = imputation or IMPUTATION_DEFAULTS
    pre  = agent_outputs['preprocessor']
    exp  = agent_outputs['experience_extractor']
    absa = agent_outputs['absa']
    cons = agent_outputs['consistency']
    qual = agent_outputs['quality']
    dom  = agent_outputs['domain_rating']
    star = agent_outputs['star_rating']
    
    # Base signals (3)
    feats = [
        star,                            # star rating (1-5)
        exp['predicted_score'],          # text-derived experience score
        dom['domain_score'],             # TF-IDF domain rating
    ]
    
    # Consistency signals (4)
    feats += [
        cons['star_text_gap'],
        cons['absolute_gap'],
        float(cons['star_inflated']),
        cons['consistency_score'],
    ]
    
    # Quality signals (4)
    feats += [
        qual['quality_score'],
        qual['helpfulness_score'],
        qual['freshness_score'],
        float(qual['verified_purchase']),
    ]
    
    # Text quality signals (4)
    feats += [
        pre['word_count'] / 500,         # normalized
        pre['vocab_richness'],
        pre['avg_sentence_length'] / 20,
        exp['model_uncertainty'],
    ]
    
    # Aspect detection signals (10 — one per aspect)
    for aspect in EARBUD_ASPECTS:
        feats.append(float(absa['aspects'][aspect]['detected']))
    
    # Aspect sentiment signals (10 — encoded as -1/0/1)
    sentiment_map = {'negative': -1, 'neutral': 0, 'positive': 1, 'not_mentioned': 0}
    for aspect in EARBUD_ASPECTS:
        feats.append(sentiment_map[absa['aspects'][aspect]['sentiment']])
    
    # Interaction features (5 — known to help)
    feats += [
        star * exp['predicted_score'],   # star × text interaction
        abs(star - dom['domain_score']), # star vs domain gap
        exp['predicted_score'] * qual['quality_score'],  # weighted experience
        cons['consistency_score'] * qual['trust_weight'],
        dom['domain_confidence'] * dom['domain_score'],
    ]
    
    return np.array(feats, dtype=np.float32)
```

### 10.2 XGBoost Bootstrap Ensemble

> **v1.1 correction:** `eval_set=[(X, y)]` removed (it evaluated on training data). Inverse-frequency sample weights implement the promised class weighting. Saved as portable JSON `fusion_ensemble.json`, not a pickle. Fusion features use OUT-OF-FOLD Agent 2 scores. (§23 #11, #17)

```python
# notebooks/05_train_fusion.ipynb

import xgboost as xgb
from sklearn.model_selection import GroupKFold
import numpy as np

def train_bootstrap_ensemble(X, y, groups, imputation_means: dict,
                             n_members=20, seed=42):
    """
    20-member bootstrap ensemble.

    IMPUTATION: `imputation_means` (a dict of feature_name→float) is stored
    alongside the model pickle.  At inference time, missing optional fields
    (helpful_votes, verified_purchase) are replaced with these means so
    production inputs match the training distribution.

    XGBoost is trained with `missing=np.nan`, meaning any np.nan in X is
    treated as a structurally missing value and gets its own split direction
    learned from data.  This gives better out-of-sample behaviour than
    always imputing a constant at training time.
    """
    members = []
    rng = np.random.RandomState(seed)
    
    for i in range(n_members):
        # Bootstrap resample (sample with replacement)
        idx = rng.choice(len(X), size=len(X), replace=True)
        X_boot, y_boot, groups_boot = X[idx], y[idx], groups[idx]
        
        model = xgb.XGBRegressor(
            n_estimators=300,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=0.1,
            reg_lambda=1.0,
            objective='reg:squarederror',
            tree_method='hist',
            missing=np.nan,    # ← learn split direction for missing values
            random_state=seed + i,
        )
        model.fit(
            X_boot, y_boot,
            eval_set=[(X, y)],
            verbose=False,
        )
        members.append(model)
        print(f"Member {i+1}/{n_members} trained")

    # Persist imputation means alongside the model so production code
    # never has to recompute or hardcode them.
    import joblib
    joblib.dump(
        {'members': members, 'imputation_means': imputation_means},
        'data/models/fusion_ensemble.pkl'
    )
    print("Saved ensemble + imputation means to data/models/fusion_ensemble.pkl")
    return members

def ensemble_predict(members, X):
    preds = np.array([m.predict(X) for m in members])
    return {
        'mean': preds.mean(axis=0),
        'std': preds.std(axis=0),
        'members': preds,
    }
```

### 10.3 Split Conformal Calibration

> **v1.1 correction:** Quantile is the ⌈(n+1)(1−α)⌉-th smallest score (`np.quantile` at `(1−α)(1+1/n)` interpolates and fails when the level exceeds 1). Normalized scores `|y−ŷ|/(σ_ens+floor)` are supported so confidence varies per review. §13.3's `ConformalCalibrator` never existed: use `vera_training.calibration`. (§23 #12)

**Why conformal prediction:** It gives a mathematically guaranteed coverage interval. If we say "90% interval," we can empirically verify that 90% of held-out reviews actually fall inside the interval. No other calibration method gives this guarantee without distributional assumptions.

**Serialization design — critical.**
`ConformalCalibrator` is split into an **offline fitter** (Colab notebook 06, uses MAPIE + sklearn) and an **online predictor** (production worker, uses only a plain float loaded from JSON).  The production container must not import MAPIE or sklearn's `MapieRegressor` — they add unnecessary boot time and pull in the full sklearn dependency graph on every worker start.

All the online path needs is `q_hat` — a single float — to compute `[pred − q_hat, pred + q_hat]`.

```python
# ── notebooks/06_calibration.ipynb  (offline, Colab only) ─────────────
# This file is NOT imported in production. It computes q_hat and saves it.

import json
import numpy as np
from mapie.regression import MapieRegressor

def fit_and_save_calibrator(members, X_cal, y_cal,
                             alpha=0.10,
                             out_path='data/models/conformal_qhat.json'):
    """
    Fit split conformal predictor on the HELD-OUT calibration set and save
    q_hat as a plain JSON float.  This is all production ever needs.

    IMPORTANT: X_cal / y_cal must be:
      (a) product-grouped — no ASIN appears in both cal and train splits
      (b) drawn from the SAME feature distribution as production inputs —
          include zero-metadata reviews, not only high-quality ones.
    """
    base_preds = np.mean([m.predict(X_cal) for m in members], axis=0)

    # Nonconformity scores: |y_true - y_hat|
    nonconf = np.abs(y_cal - base_preds)

    # Finite-sample-corrected quantile (Venn–Abers / split-CP guarantee)
    n = len(y_cal)
    q_hat = float(np.quantile(nonconf, (1 - alpha) * (1 + 1 / n)))

    # Empirical coverage check (must be ≥ nominal before saving)
    intervals_lo = np.clip(base_preds - q_hat, 1.0, 5.0)
    intervals_hi = np.clip(base_preds + q_hat, 1.0, 5.0)
    empirical_coverage = float(np.mean(
        (y_cal >= intervals_lo) & (y_cal <= intervals_hi)
    ))
    assert empirical_coverage >= (1 - alpha - 0.02), (
        f"Coverage {empirical_coverage:.3f} below nominal {1-alpha:.3f}. "
        "Widen calibration set or re-check feature distribution."
    )

    payload = {
        'q_hat':              q_hat,
        'alpha':              alpha,
        'empirical_coverage': empirical_coverage,
        'nominal_coverage':   1 - alpha,
        'calibration_n':      n,
    }
    with open(out_path, 'w') as f:
        json.dump(payload, f, indent=2)

    print(f"Saved q_hat={q_hat:.4f}  "
          f"(empirical coverage {empirical_coverage:.1%} vs target {1-alpha:.0%})")
    return q_hat


# ── backend/app/ml/calibration/conformal.py  (production runtime) ─────
# Loaded once at worker startup.  No MAPIE, no sklearn, just a float.

import json
import numpy as np


class ConformalPredictor:
    """
    Production-only conformal interval predictor.
    Reads the pre-fitted q_hat float from JSON — zero sklearn overhead.
    No fitting, no MAPIE, no heavy imports.
    """

    def __init__(self, qhat_path: str = 'data/models/conformal_qhat.json'):
        with open(qhat_path) as f:
            data = json.load(f)
        self.q_hat            = float(data['q_hat'])
        self.nominal_coverage = float(data['nominal_coverage'])
        self._meta            = data   # keep for /health diagnostics

    def predict_interval(self, base_pred: float) -> tuple[float, float, float]:
        """
        Return (lower, upper, confidence) for a single review prediction.

        Confidence is inversely proportional to interval width.
        Max possible gap = 4 (scale runs 1–5), so a 0.5-unit interval
        scores 87.5% confidence, a 2-unit interval scores 50%.
        """
        lower = float(np.clip(base_pred - self.q_hat, 1.0, 5.0))
        upper = float(np.clip(base_pred + self.q_hat, 1.0, 5.0))
        width = upper - lower
        confidence = float(np.clip(1.0 - width / 4.0, 0.0, 1.0))
        return lower, upper, confidence

    def health_info(self) -> dict:
        """Expose calibration metadata for the /health endpoint."""
        return {
            'q_hat':            self.q_hat,
            'nominal_coverage': self.nominal_coverage,
        }
```

**Notebook 06 checklist before saving `q_hat`:**
- [ ] Calibration set is product-grouped (zero ASIN overlap with train)
- [ ] Calibration set includes zero-`helpful_votes` reviews (matches production)
- [ ] `empirical_coverage ≥ nominal − 2%` asserted before `json.dump`
- [ ] `conformal_qhat.json` uploaded to HuggingFace Hub alongside ONNX models
- [ ] `CALIBRATION_CHECKPOINTS` table in DB updated with the fitted values

---

## 11. Product Aggregation — Empirical Bayes

### 11.1 Why Empirical Bayes

A product with 1 review scoring 5.0 should NOT outrank a product with 500 reviews averaging 4.6. Empirical Bayes "shrinks" estimates from data-sparse products toward the global mean, proportional to how unreliable those estimates are.

For product `j`, use a quality-weighted mean `m_j`, Kish effective sample size
`n_eff = (Σw)² / Σw²`, and sampling variance `s²_j = σ²_j / n_eff`. The
shrinkage factor is `B_j = s²_j / (s²_j + τ²)`, where `τ²` is the
between-product variance estimated from product means after subtracting average
sampling variance. Products with many reliable reviews have small `s²_j` and
little shrinkage. A one-review product uses a conservative variance prior rather
than a spuriously tiny pooled variance.

### 11.2 Implementation

> **v1.1 correction:** τ² is the BETWEEN-product variance (method of moments), not the variance of all review scores; weighted means use the Kish effective n; single-review products use the pooled within-product variance; uncertainty is the posterior sd `sqrt(B·τ²)`. All products are re-aggregated together so the prior and ranks stay consistent. (§23 #13–14)

```python
# backend/app/ml/calibration/empirical_bayes.py

import numpy as np
from dataclasses import dataclass

@dataclass
class ProductAggregate:
    product_asin: str
    corrected_score: float
    uncertainty: float
    review_count: int
    trust_weighted_score: float
    eb_shrinkage_factor: float
    aspect_summary: dict

class EmpiricalBayesAggregator:
    """
    Compute trust-weighted, EB-shrunk product scores.
    Honest treatment of data sparsity — few reviews → more uncertainty.
    """
    
    def fit(self, all_corrected_scores: list[float]):
        """Estimate global mean and variance from all reviews."""
        scores = np.array(all_corrected_scores)
        self.global_mean = float(scores.mean())
        self.global_std = float(scores.std())
        # τ² must be estimated from product means less their sampling variance;
        # individual-score variance incorrectly mixes signal and noise.
        self.tau_sq = estimate_between_product_variance(...)
    
    def aggregate_product(self, 
                          corrected_scores: list[float],
                          quality_weights: list[float],
                          aspect_sentiments: list[dict]) -> ProductAggregate:
        
        scores = np.array(corrected_scores)
        weights = np.array(quality_weights)
        weights = weights / weights.sum()  # normalize
        
        # Trust-weighted mean
        weighted_mean = float(np.average(scores, weights=weights))
        
        # Within-product variance (σ²).
        # Noise floor of 0.05 prevents sigma_sq = 0 when all n reviews agree
        # exactly (e.g. [4.0, 4.0]).  Without the floor B = 0/(0+τ²) = 0,
        # meaning a 2-review product gets *no* shrinkage — clearly wrong.
        n = len(scores)
        raw_var = float(np.var(scores)) if n > 1 else 0.5
        sigma_sq = max(raw_var, 0.05)          # ← noise floor
        
        # Shrinkage factor B = σ²/n / (σ²/n + τ²)
        # As n → ∞, B → 0 (no shrinkage); as n → 1, B → large shrinkage
        B = (sigma_sq / n) / ((sigma_sq / n) + self.tau_sq)
        B = float(np.clip(B, 0, 1))
        
        # EB estimate: shrink toward global mean
        eb_score = (1 - B) * weighted_mean + B * self.global_mean
        
        # Posterior standard deviation of the normal-normal EB estimate.
        uncertainty = float(np.sqrt(B * self.tau_sq))
        
        # Aggregate aspect sentiment (majority vote per aspect)
        aspect_summary = self._aggregate_aspects(aspect_sentiments)
        
        return ProductAggregate(
            product_asin='',  # set by caller
            corrected_score=round(float(np.clip(eb_score, 1, 5)), 2),
            uncertainty=round(uncertainty, 3),
            review_count=n,
            trust_weighted_score=round(weighted_mean, 2),
            eb_shrinkage_factor=round(B, 3),
            aspect_summary=aspect_summary,
        )
    
    def _aggregate_aspects(self, aspect_sentiments: list[dict]) -> dict:
        summary = {}
        for aspect in EARBUD_ASPECTS:
            mentions = [a[aspect] for a in aspect_sentiments 
                       if a[aspect]['detected']]
            if not mentions:
                summary[aspect] = {'detected_fraction': 0.0, 'dominant_sentiment': 'not_mentioned'}
                continue
            
            sentiments = [m['sentiment'] for m in mentions]
            from collections import Counter
            dominant = Counter(sentiments).most_common(1)[0][0]
            summary[aspect] = {
                'detected_fraction': round(len(mentions) / len(aspect_sentiments), 2),
                'dominant_sentiment': dominant,
            }
        return summary
```

---

## 12. Model Fine-tuning Guide (Colab)

### 12.1 Connecting VS Code to Colab

```python
# Cell 1 of any Colab notebook — run this to enable VS Code connection
!pip install jupyter_http_over_ws -q
import urllib.request
urllib.request.urlretrieve(
    'https://raw.githubusercontent.com/googlecolab/colabtools/master/packages/colab-cdn-widget-manager/install.sh',
    'install.sh'
)
# Then in VS Code: Ctrl+Shift+P → "Jupyter: Specify local or remote server"
# Paste the runtime URL from Colab's "Connect to hosted runtime" dialog
```

### 12.2 Fine-tuning DeBERTa-v3-base (Notebook 04)

> **v1.1 correction:** Use `vera_training.finetune`: 5 product-grouped cross-fitted models produce out-of-fold scores, then a final model on all labels. `evaluation_strategy` → `eval_strategy`; dynamic padding. (§23 #17)

```python
# notebooks/04_finetune_experience.ipynb
# Run on Colab T4 GPU (free) — takes ~45 minutes

!pip install transformers datasets accelerate -q

import torch
from transformers import (
    AutoTokenizer, AutoModelForSequenceClassification,
    TrainingArguments, Trainer, EarlyStoppingCallback
)
from datasets import Dataset
import numpy as np
import json

# Load our labels
with open('data/labels/labels_v1.jsonl') as f:
    labels = [json.loads(line) for line in f]

# Merge with review text
labels_df = pd.DataFrame(labels)
merged = labels_df.merge(labeling_pool, left_on='review_id', right_index=True)

# Product-grouped train/val split (NO leakage)
from sklearn.model_selection import GroupShuffleSplit
gss = GroupShuffleSplit(n_splits=1, test_size=0.15, random_state=42)
train_idx, val_idx = next(gss.split(merged, groups=merged['parent_asin']))
train_df = merged.iloc[train_idx]
val_df   = merged.iloc[val_idx]

print(f"Train: {len(train_df)}, Val: {len(val_df)}")

# Tokenize
tokenizer = AutoTokenizer.from_pretrained('microsoft/deberta-v3-base')

def tokenize(batch):
    return tokenizer(
        batch['text'], 
        truncation=True, 
        max_length=512,
        padding='max_length'
    )

train_ds = Dataset.from_pandas(train_df[['text', 'experience_score']])
val_ds   = Dataset.from_pandas(val_df[['text', 'experience_score']])
train_ds = train_ds.map(tokenize, batched=True)
val_ds   = val_ds.map(tokenize, batched=True)
train_ds = train_ds.rename_column('experience_score', 'labels')
val_ds   = val_ds.rename_column('experience_score', 'labels')
train_ds.set_format('torch')
val_ds.set_format('torch')

# Model: regression head (num_labels=1)
model = AutoModelForSequenceClassification.from_pretrained(
    'microsoft/deberta-v3-base',
    num_labels=1,
    problem_type='regression',
)

# Training args
args = TrainingArguments(
    output_dir='./vera_experience_model',
    num_train_epochs=5,
    per_device_train_batch_size=8,
    per_device_eval_batch_size=16,
    warmup_ratio=0.1,
    weight_decay=0.01,
    learning_rate=2e-5,
    evaluation_strategy='epoch',
    save_strategy='epoch',
    load_best_model_at_end=True,
    metric_for_best_model='eval_loss',
    fp16=True,    # T4 GPU supports FP16
    logging_steps=20,
    report_to='none',
)

def compute_metrics(eval_pred):
    preds, labels = eval_pred
    preds = preds.flatten()
    mae = np.mean(np.abs(preds - labels))
    return {'mae': mae}

trainer = Trainer(
    model=model,
    args=args,
    train_dataset=train_ds,
    eval_dataset=val_ds,
    compute_metrics=compute_metrics,
    callbacks=[EarlyStoppingCallback(early_stopping_patience=2)],
)

trainer.train()

# Save to HuggingFace Hub
model.push_to_hub('YOUR_HF_USERNAME/vera-experience-deberta')
tokenizer.push_to_hub('YOUR_HF_USERNAME/vera-experience-deberta')
```

### 12.3 ONNX Export + INT8 Quantization

> **v1.1 correction:** `onnxruntime.quantization.quantize_dynamic` replaces the AVX-512-VNNI-specific config. G2 parity is checked PyTorch vs FP32 ONNX through the production tokenizer; INT8 drift is reported separately. Artifact names: see `app.ml.models.loader.REQUIRED_ARTIFACTS`.

```python
# Run AFTER fine-tuning

!pip install optimum[exporters] -q

from optimum.exporters.onnx import main_export
from optimum.onnxruntime import ORTQuantizer
from optimum.onnxruntime.configuration import AutoQuantizationConfig

# Export to ONNX
main_export(
    model_name_or_path='YOUR_HF_USERNAME/vera-experience-deberta',
    output='./experience_onnx',
    task='sequence-classification',
    opset=14,
)

# INT8 Static Quantization (2-4x speedup, ~75% size reduction)
quantizer = ORTQuantizer.from_pretrained('./experience_onnx')
qconfig = AutoQuantizationConfig.avx512_vnni(is_static=False, per_channel=False)
quantizer.quantize(
    save_dir='./experience_onnx_quantized',
    quantization_config=qconfig,
)

# Verify size
import os
orig = os.path.getsize('./experience_onnx/model.onnx') / 1e6
quant = os.path.getsize('./experience_onnx_quantized/model_quantized.onnx') / 1e6
print(f"Original: {orig:.1f}MB → Quantized: {quant:.1f}MB")
# Expected: ~730MB → ~90MB

# Upload quantized model to HuggingFace Hub
from huggingface_hub import HfApi
api = HfApi()
api.upload_file(
    path_or_fileobj='./experience_onnx_quantized/model_quantized.onnx',
    path_in_repo='experience_model.onnx',
    repo_id='YOUR_HF_USERNAME/vera-models',
    repo_type='model',
)
```

---

## 13. Evaluation Protocol

**Non-negotiable rule:** Every number reported must come from the evaluation protocol below. No single-split numbers. No cherry-picked holdouts.

### 13.1 Cross-Validation Design

> **v1.1 correction:** `RepeatedGroupKFold` does not exist in scikit-learn. Implemented as 5 product-grouped folds × 3 repeats = 15 folds in `vera_training.splits.repeated_group_folds`. (§23 #20)

```mermaid
flowchart LR
    ALL[2000 Labeled\nReviews] --> SPLIT[15-Fold Repeated\nProduct-Grouped CV]
    SPLIT --> F1[Fold 1\nTrain 85% / Test 15%]
    SPLIT --> FN[... Folds 2–14 ...]
    SPLIT --> F15[Fold 15\nTrain 85% / Test 15%]
    F1 --> M1[Metric 1]
    FN --> MN[...]
    F15 --> M15[Metric 15]
    M1 --> REPORT[Report: Mean ± Std\nFold Win Rate\nPaired Wilcoxon p-value]
```

```python
# notebooks/07_ablation_study.ipynb

from sklearn.model_selection import RepeatedGroupKFold
from scipy.stats import wilcoxon
import numpy as np

def run_cv(X, y, groups, model_factory, n_splits=15, n_repeats=1):
    """
    Product-grouped cross-validation.
    Groups = product ASINs. Reviews from same product NEVER split across folds.
    """
    cv = RepeatedGroupKFold(n_splits=n_splits, n_repeats=n_repeats, random_state=42)
    maes = []
    
    for fold, (train_idx, test_idx) in enumerate(cv.split(X, y, groups)):
        X_tr, X_te = X[train_idx], X[test_idx]
        y_tr, y_te = y[train_idx], y[test_idx]
        
        model = model_factory()
        model.fit(X_tr, y_tr)
        preds = model.predict(X_te)
        
        mae = np.mean(np.abs(preds - y_te))
        maes.append(mae)
    
    return np.array(maes)

# Run for baseline and VERA
maes_baseline = run_cv(X_star_only, y, groups, lambda: Ridge())
maes_vera     = run_cv(X_full, y, groups, lambda: build_ensemble())

# Paired comparison
stat, p_value = wilcoxon(maes_baseline, maes_vera, alternative='greater')
win_rate = (maes_baseline > maes_vera).mean()

print(f"Stars-only:  {maes_baseline.mean():.3f} ± {maes_baseline.std():.3f}")
print(f"VERA full:   {maes_vera.mean():.3f} ± {maes_vera.std():.3f}")
print(f"Win rate: {win_rate:.1%}  |  Wilcoxon p = {p_value:.4f}")
```

### 13.2 Ablation Study (Which Agents Actually Help)

```python
ABLATION_CONFIGS = {
    'stars_only':          ['star'],
    '+experience':         ['star', 'experience'],
    '+domain':             ['star', 'experience', 'domain'],
    '+consistency':        ['star', 'experience', 'domain', 'consistency'],
    '+quality':            ['star', 'experience', 'domain', 'consistency', 'quality'],
    '+absa':               ['star', 'experience', 'domain', 'consistency', 'quality', 'absa'],
    'full_vera':           ['star', 'experience', 'domain', 'consistency', 'quality', 'absa'],
}

# Run cross-val for every config, report results table
# Only keep a component if it improves MAE and win_rate > 60%
```

### 13.3 Calibration Verification

```python
# Verify conformal coverage empirically
alpha_targets = [0.05, 0.10, 0.20]  # 95%, 90%, 80% intervals

for alpha in alpha_targets:
    calibrator = ConformalCalibrator().fit(members, X_cal, y_cal, alpha=alpha)
    coverage_result = calibrator.verify_coverage(members, X_test, y_test)
    print(f"Target {1-alpha:.0%}: Empirical {coverage_result['empirical_coverage']:.1%} "
          f"{'✓' if coverage_result['covered'] else '✗'}")
```

### 13.4 Per-Aspect Evaluation

```python
# For each aspect:
# 1. Detection F1: binary (mentioned vs not_mentioned)
# 2. Sentiment accuracy: among detected, what fraction has correct sentiment

from sklearn.metrics import f1_score, accuracy_score

for aspect in EARBUD_ASPECTS:
    # Detection
    y_det_true = [1 if l['aspects'][aspect]['mentioned'] else 0 for l in y_test_labels]
    y_det_pred = [1 if absa_output[aspect]['detected'] else 0 for absa_output in preds]
    det_f1 = f1_score(y_det_true, y_det_pred)
    
    # Sentiment (on detected-only subset)
    # ...
    print(f"{aspect}: detection F1={det_f1:.3f}")
```

---

## 14. API Design

### 14.1 Endpoint Map

```mermaid
sequenceDiagram
    participant C as Client
    participant API as FastAPI
    participant RD as Redis Queue
    participant WK as Celery Worker
    participant DB as PostgreSQL

    C->>API: POST /api/reviews {text, star, meta}
    API->>DB: Insert review (status=pending)
    API->>RD: Enqueue task(review_id)
    API-->>C: 202 Accepted {task_id, review_id}

    loop Poll (or WebSocket)
        C->>API: GET /api/reviews/{id}/status
        API->>DB: Fetch status
        API-->>C: {status: processing | done}
    end

    WK->>RD: Dequeue task
    WK->>DB: Fetch review text
    WK->>WK: Run 7-agent pipeline
    WK->>DB: Update review (score + aspects)

    C->>API: GET /api/reviews/{id}
    API->>DB: Fetch complete review
    API-->>C: {corrected_score, interval, aspects, ...}
```

### 14.2 FastAPI Routes

> **v1.1 correction:** Routes are sync `def` (sync SQLAlchemy inside `async def` blocks the event loop). Submission writes review + `jobs` row in one transaction and never returns 503 on broker outage. Products listing hides unscored shells, adds `star_average`/`rank_position` sorts and `X-Total-Count`; detail paginates reviews. (§23 #15–16)

```python
# backend/app/api/routes/reviews.py

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.schemas.review import ReviewCreate, ReviewResponse, ReviewStatus
from app.worker.tasks import process_review_task
from app.api.deps import get_db

router = APIRouter(prefix='/api/reviews', tags=['reviews'])

@router.post('/', response_model=ReviewStatus, status_code=202)
async def submit_review(
    review: ReviewCreate,
    db: Session = Depends(get_db)
):
    """
    Submit a review for processing.
    Returns immediately with a task_id for polling.
    """
    db_review = Review(
        text=review.text,
        star_rating=review.star_rating,
        helpful_votes=review.helpful_votes or 0,
        verified_purchase=review.verified_purchase or False,
        product_title=review.product_title or '',
        product_asin=review.product_asin or '',
        status='pending',
    )
    db.add(db_review)
    db.commit()
    db.refresh(db_review)
    
    # Enqueue async processing
    task = process_review_task.delay(db_review.id)
    
    return ReviewStatus(
        review_id=db_review.id,
        task_id=task.id,
        status='pending',
        message='Review queued for processing',
    )

@router.get('/{review_id}', response_model=ReviewResponse)
async def get_review(review_id: int, db: Session = Depends(get_db)):
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(404, 'Review not found')
    return review

@router.get('/{review_id}/status', response_model=ReviewStatus)
async def get_review_status(review_id: int, db: Session = Depends(get_db)):
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(404, 'Review not found')
    return ReviewStatus(
        review_id=review.id,
        task_id=None,
        status=review.status,
        message='Completed' if review.status == 'done' else 'Processing',
    )

# === Product Routes ===
# backend/app/api/routes/products.py

@router.get('/', response_model=list[ProductResponse])
async def list_products(
    sort_by: str = 'corrected_score',   # or 'review_count', 'uncertainty'
    order: str = 'desc',
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Get product rankings, sorted by corrected EB score."""
    ...

@router.get('/{asin}', response_model=ProductDetailResponse)
async def get_product(asin: str, db: Session = Depends(get_db)):
    """Get product detail including all reviews and aspect breakdown."""
    ...
```

### 14.3 Pydantic Schemas

```python
# backend/app/schemas/review.py

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum

class AspectSentiment(BaseModel):
    detected: bool
    sentiment: str   # positive | negative | neutral | not_mentioned
    confidence: float

class ReviewCreate(BaseModel):
    text: str = Field(..., min_length=20, max_length=10000)
    star_rating: float = Field(..., ge=1, le=5)
    helpful_votes: Optional[int] = 0
    verified_purchase: Optional[bool] = False
    product_title: Optional[str] = ''
    product_asin: Optional[str] = ''

class ReviewResponse(BaseModel):
    id: int
    text: str
    star_rating: float
    corrected_score: Optional[float]
    interval_lower: Optional[float]
    interval_upper: Optional[float]
    confidence_value: Optional[float]
    star_text_gap: Optional[float]
    review_quality: Optional[float]
    aspects: Optional[dict[str, AspectSentiment]]
    status: str
    
    class Config:
        from_attributes = True
```

### 14.4 Celery Config (Upstash-safe)

```python
# backend/app/worker/celery_app.py
#
# UPSTASH BUDGET: free tier = 10,000 Redis commands/day.
# Default Celery Redis polling_interval = 0.1 s → 864,000 poll commands/day
# per worker before any real work happens.  Two workers = 1.7M commands —
# 170× the free-tier budget just from idle polling.
#
# Fix: polling_interval = 2.0 s → 43,200 polls/worker/day.
# Two workers = 86,400 polling commands + ~5 commands/review processed.
# For ≤ 500 reviews/day that stays well under 10K ONLY with a single worker.
# For higher volume, upgrade to Upstash paid or add a Redis connection pool
# with long-poll BLPOP instead of Celery's default busy-wait.
#
# result_expires = 3600 auto-deletes finished task tombstones so result keys
# don't pile up indefinitely in Redis.

from celery import Celery
from app.config import settings

celery_app = Celery('vera', broker=settings.REDIS_URL, backend=settings.REDIS_URL)

celery_app.conf.update(
    task_serializer            = 'json',
    result_serializer          = 'json',
    accept_content             = ['json'],
    timezone                   = 'UTC',
    enable_utc                 = True,
    result_expires             = 3600,      # auto-delete result keys after 1 h
    broker_transport_options   = {
        'visibility_timeout':  3600,        # re-queue if worker dies within 1 h
        'polling_interval':    2.0,         # ← raised from 0.1 s to save cmds
    },
    worker_prefetch_multiplier = 1,         # one task at a time per slot
    task_acks_late             = True,      # ack only after task completes
)
```

### 14.5 Celery Tasks

> **v1.1 correction:** Replaced by a transactional outbox: `vera.run_job(job_id)` executes review/aggregate jobs with durable retries in the DB; the sketch loaded models at import in the API process, crashed on a missing review, and marked reviews `failed` while still retrying. (§23 #15)

```python
# backend/app/worker/tasks.py

from app.worker.celery_app import celery_app
from app.ml.pipeline import VERAPipeline
from app.database import SessionLocal

pipeline = VERAPipeline()   # load models ONCE at worker startup

@celery_app.task(bind=True, max_retries=3, default_retry_delay=5)
def process_review_task(self, review_id: int):
    db = SessionLocal()
    try:
        review = db.query(Review).filter(Review.id == review_id).first()
        review.status = 'processing'
        db.commit()

        result = pipeline.process(
            text=review.text,
            star_rating=review.star_rating,
            helpful_votes=review.helpful_votes,
            verified_purchase=review.verified_purchase,
            product_title=review.product_title,
        )

        review.corrected_score   = result['corrected_score']
        review.interval_lower    = result['interval'][0]
        review.interval_upper    = result['interval'][1]
        review.confidence_value  = result['confidence']
        review.star_text_gap     = result['star_text_gap']
        review.review_quality    = result['review_quality']
        review.aspects           = result['aspects']
        review.status            = 'done'
        db.commit()

        # Only trigger aggregation when we have a real, non-empty ASIN.
        # An empty string would race against other empty-string reviews
        # and write a corrupt "product" row keyed to '' in the DB.
        asin = (review.product_asin or '').strip()
        if asin:
            aggregate_product_task.delay(asin)

    except Exception as exc:
        review.status = 'failed'
        db.commit()
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=5, default_retry_delay=10)
def aggregate_product_task(self, product_asin: str):
    """
    Re-compute the Empirical Bayes product score after a new review lands.

    RACE CONDITION GUARD: multiple reviews for the same ASIN can finish at
    the same time, causing concurrent writes to the `products` table.
    We acquire a per-ASIN Redis lock before touching the DB.  If the lock
    is already held (another worker is aggregating this ASIN), we back off
    and retry — the other worker's result will already be fresh enough.
    """
    if not product_asin:
        return

    from redis import Redis
    redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    lock_key = f"agg_lock:{product_asin}"

    lock = redis_client.lock(lock_key, timeout=30, blocking_timeout=5)
    acquired = lock.acquire(blocking=True)

    if not acquired:
        # Another worker just aggregated this product — retry once to pick
        # up any further reviews that arrived while we waited.
        raise self.retry(countdown=12)

    db = SessionLocal()
    try:
        reviews = (db.query(Review)
                   .filter(Review.product_asin == product_asin,
                           Review.status == 'done',
                           Review.corrected_score.isnot(None))
                   .all())

        if not reviews:
            return

        corrected_scores  = [r.corrected_score for r in reviews]
        quality_weights   = [r.review_quality or 0.5 for r in reviews]
        aspect_sentiments = [r.aspects or {} for r in reviews]

        aggregate = eb_aggregator.aggregate_product(
            corrected_scores, quality_weights, aspect_sentiments
        )

        product = (db.query(Product)
                   .filter(Product.asin == product_asin)
                   .first())
        if product is None:
            product = Product(asin=product_asin)
            db.add(product)

        product.corrected_score       = aggregate.corrected_score
        product.uncertainty           = aggregate.uncertainty
        product.trust_weighted_score  = aggregate.trust_weighted_score
        product.eb_shrinkage_factor   = aggregate.eb_shrinkage_factor
        product.review_count          = aggregate.review_count
        product.aspect_summary        = aggregate.aspect_summary
        product.last_aggregated_at    = datetime.utcnow()
        db.commit()

    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()
        try:
            lock.release()
        except Exception:
            pass  # lock TTL already expired — harmless
```

---

## 15. Database Schema

> **v1.1 correction:** `reviews.product_asin` FK kept; a product shell is created before the first review (the v1.0 flow violated the FK). New columns: reviews `flags`, `explanation`, `error_message` (metadata columns nullable = "not supplied"); products `star_average`, `previous_rank_position`, `created_at`; calibration `method`. New table `jobs` (migration 002). (§23 #16)

```mermaid
erDiagram
    REVIEWS {
        int id PK
        text text
        float star_rating
        int helpful_votes
        bool verified_purchase
        string product_title
        string product_asin FK
        float corrected_score
        float interval_lower
        float interval_upper
        float confidence_value
        float star_text_gap
        float review_quality
        json aspects
        string status
        timestamp created_at
        timestamp updated_at
    }

    PRODUCTS {
        string asin PK
        string title
        float corrected_score
        float uncertainty
        float trust_weighted_score
        float eb_shrinkage_factor
        int review_count
        json aspect_summary
        int rank_position
        timestamp last_aggregated_at
    }

    LABEL_RUNS {
        int id PK
        string review_text_hash
        string labeler
        float experience_score
        json aspects
        bool has_irony
        string review_quality
        json raw_response
        timestamp created_at
    }

    CALIBRATION_CHECKPOINTS {
        int id PK
        float q_hat
        float empirical_coverage
        float nominal_coverage
        int calibration_set_size
        timestamp fitted_at
    }

    REVIEWS }o--|| PRODUCTS : "product_asin"
```

### 15.1 Alembic Migration

```python
# migrations/versions/001_initial.py

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

def upgrade():
    op.create_table('products',
        sa.Column('asin', sa.String(20), primary_key=True),
        sa.Column('title', sa.Text()),
        sa.Column('corrected_score', sa.Float()),
        sa.Column('uncertainty', sa.Float()),
        sa.Column('trust_weighted_score', sa.Float()),
        sa.Column('eb_shrinkage_factor', sa.Float()),
        sa.Column('review_count', sa.Integer(), default=0),
        sa.Column('aspect_summary', JSONB()),
        sa.Column('rank_position', sa.Integer()),
        sa.Column('last_aggregated_at', sa.DateTime(timezone=True)),
    )
    
    op.create_table('reviews',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('star_rating', sa.Float(), nullable=False),
        sa.Column('helpful_votes', sa.Integer(), default=0),
        sa.Column('verified_purchase', sa.Boolean(), default=False),
        sa.Column('product_title', sa.Text()),
        sa.Column('product_asin', sa.String(20), sa.ForeignKey('products.asin')),
        sa.Column('corrected_score', sa.Float()),
        sa.Column('interval_lower', sa.Float()),
        sa.Column('interval_upper', sa.Float()),
        sa.Column('confidence_value', sa.Float()),
        sa.Column('star_text_gap', sa.Float()),
        sa.Column('review_quality', sa.Float()),
        sa.Column('aspects', JSONB()),
        sa.Column('status', sa.String(20), default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    
    op.create_index('idx_reviews_asin', 'reviews', ['product_asin'])
    op.create_index('idx_reviews_status', 'reviews', ['status'])
    op.create_index('idx_products_rank', 'products', ['rank_position'])
```

---

## 16. Frontend Design System

### 16.1 Design Philosophy

VERA is a **truth-telling tool** — it exposes what star ratings hide. The UI must reflect this: clinical precision, not marketing warmth. Think data observatory, not e-commerce storefront.

**Design direction:** Dark-mode primary. High contrast. Data-forward. Every UI element earns its place by communicating information.

**Color palette:**
```css
:root {
  --bg-primary:     #080B12;   /* Near-black, slightly blue-tinted */
  --bg-surface:     #0F1420;   /* Card surface */
  --bg-elevated:    #161D2E;   /* Elevated elements */
  --accent-primary: #4B7BE5;   /* Electric blue — corrected score */
  --accent-success: #10D98C;   /* Teal green — positive aspects */
  --accent-warning: #F5A623;   /* Amber — consistency warnings */
  --accent-danger:  #E85353;   /* Red — negative aspects */
  --text-primary:   #E8ECF0;
  --text-secondary: #8A94A6;
  --text-muted:     #4E5C72;
  --border:         #1E2A3E;
  --border-active:  #2E3F5C;
}
```

**Typography:**
- Headlines: `Inter` 700 — bold, technical
- Body: `Inter` 400 — clean, readable
- Data/numbers: `JetBrains Mono` — monospace for scores and intervals (numbers should feel precise, not decorative)

### 16.2 Key UI Components

#### ScoreCard (hero component)

```
┌──────────────────────────────────────────┐
│  ★ Star Rating  →  ◆ Corrected Score    │
│                                           │
│    ★★★★★  5.0      ◆ 3.2               │
│                   ± [2.8 ──────── 3.7]  │
│                      confidence: 74%     │
│                                           │
│  "Sound quality mentioned as a major     │
│   concern — text implies 3-star despite  │
│   the 5-star click."                     │
└──────────────────────────────────────────┘
```

Framer Motion animation: star counter stays static; corrected score animates from 0 to final value over 1.2s with a spring easing, making the difference viscerally obvious.

#### AspectRadar (aspect breakdown)

10-axis radar chart using Recharts `RadarChart`. Each axis = one aspect. Color = sentiment (teal for positive, red for negative, gray for not mentioned). Axis only shows if detected.

#### ConfidenceBar (interval visualization)

```
1.0           [●══════════●]         5.0
              2.8         3.7
              ↑ lower     ↑ upper
              ←── 0.9-wide interval ───→
```

Custom SVG component — not a standard progress bar. The dot represents the point estimate, the bar the interval.

#### ProductTable (rankings)

Sortable by: corrected score (default), raw star average, review count, uncertainty. Each row shows: rank change indicator, star vs corrected comparison, aspect mini-icons, review count badge.

### 16.3 Key Animations

**Rule:** One orchestrated entrance per page load. No scattered hover effects. Actions get transitions.

```tsx
// components/ScoreCard.tsx

import { motion, useSpring, useTransform } from 'framer-motion'

function AnimatedScore({ target }: { target: number }) {
  const raw = useSpring(0, { stiffness: 80, damping: 25 })
  
  useEffect(() => { raw.set(target) }, [target])
  
  const display = useTransform(raw, (v) => v.toFixed(1))
  
  return <motion.span>{display}</motion.span>
}

// Page entrance: staggered reveal
const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.08, delayChildren: 0.1 }
  }
}

const itemVariants = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.2, 0, 0, 1] } }
}
```

### 16.4 Pages

| Page | Route | Primary Job |
|---|---|---|
| **Landing** | `/` | Submit a review, see immediate results |
| **Product Rankings** | `/products` | Browse all products, sorted by corrected score |
| **Product Detail** | `/products/[asin]` | Full aspect breakdown + all reviews with scores |

---

## 17. Deployment Architecture

### 17.1 Render Setup (Backend)

> **v1.2 correction:** No Render database (Supabase is the DB). The free 512 MB service is not
> suitable for the FP32 model worker. Do not deploy the current Render blueprint as production;
> select a user-approved runtime with sufficient memory, verify peak RSS with complete artifacts,
> and run migrations at startup. (§23 #23, #28)

```yaml
# render.yaml (in repo root)
services:
  - type: web
    name: vera-api
    env: python
    region: oregon
    plan: free
    buildCommand: |
      pip install -r backend/requirements.txt
      cd backend && alembic upgrade head
    startCommand: cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: vera-db
          property: connectionString
      - key: REDIS_URL
        sync: false  # set manually from Upstash
    healthCheckPath: /health

  - type: worker
    name: vera-worker
    env: python
    region: oregon
    plan: free
    buildCommand: pip install -r backend/requirements.txt
    startCommand: cd backend && celery -A app.worker.celery_app worker --loglevel=info --concurrency=2
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: vera-db
          property: connectionString

databases:
  - name: vera-db
    databaseName: vera
    user: vera_user
    plan: free
```

**Cold start prevention:** Set up UptimeRobot to ping `https://vera-api.onrender.com/health` every 5 minutes. This keeps the free tier from sleeping.

### 17.2 Vercel Setup (Frontend)

> **v1.1 correction:** The frontend proxy reads server-side `API_URL` (not a `NEXT_PUBLIC_` variable).

```bash
# In frontend/ directory
vercel

# Set environment variables
vercel env add NEXT_PUBLIC_API_URL    # your Render API URL
```

```javascript
// frontend/next.config.js
module.exports = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL}/api/:path*`,
      },
    ]
  },
}
```

### 17.3 Model Loading at Startup

> **v1.1 correction:** Artifacts download into `MODEL_DIR`; the worker exits if any is missing (no fallback). CLI: `cd backend && python -m app.ml.models.loader [--check]`.

```python
# backend/app/ml/models/loader.py
# Models are downloaded from HuggingFace Hub at worker startup
# Cached locally to avoid re-downloading on each restart

import os
from huggingface_hub import hf_hub_download
from pathlib import Path

MODEL_CACHE = Path('./model_cache')
MODEL_CACHE.mkdir(exist_ok=True)

def ensure_models():
    """Download ONNX models from HF Hub if not cached."""
    models = {
        'experience_model.onnx': ('YOUR_HF_USERNAME/vera-models', 'experience_model.onnx'),
        'absa_model.onnx':       ('YOUR_HF_USERNAME/vera-models', 'absa_model.onnx'),
        'domain_tfidf.pkl':      ('YOUR_HF_USERNAME/vera-models', 'domain_tfidf.pkl'),
    }
    
    for local_name, (repo_id, filename) in models.items():
        local_path = MODEL_CACHE / local_name
        if not local_path.exists():
            print(f"Downloading {local_name}...")
            hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                local_dir=MODEL_CACHE,
                token=os.environ.get('HF_TOKEN'),
            )
    print("All models ready.")

# Call at app startup
ensure_models()
```

### 17.4 Resource Budget (Free Tier)

| Resource | Budget | Usage |
|---|---|---|
| Backend RAM | ≥ 2 GiB starting allocation | FP32 worker requirement; verify peak RSS with the complete artifact set before deployment (§23 #28) |
| Render CPU | 0.1 vCPU shared | Async via Celery, latency target 5–10s per review |
| Supabase DB | 500 MB | ~10K reviews × 5KB/review = 50MB ✓ |
| Upstash Redis | 10K cmds/day | ~5 cmds/review → 2,000 reviews/day ✓ |
| Label provider | Organization/model quotas apply | Current labeling uses configured Groq providers; quota and throughput are not a fixed product budget |
| Vercel | Unlimited hobby | Static + SSR, no compute limits for our scale ✓ |

---

## 18. CI/CD Pipeline

> **v1.1 correction:** CI installs `requirements-lint.txt` + `requirements-test.txt` (the v1.0 job ran ruff/black/mypy without installing them), runs the migration round-trip and frontend `lint`/`typecheck`/`build`. `deploy.yml` reuses CI, then triggers the Render deploy hook and Vercel. (§23 #24)

```mermaid
flowchart LR
    DEV[Push to\nfeature branch] --> PR[Open Pull Request\non GitHub]
    PR --> CI[GitHub Actions\nCI Workflow]
    CI --> LINT[Ruff linting\nBlack formatting]
    CI --> TEST[pytest\nunit + integration]
    CI --> TYPE[mypy\ntype checking]
    LINT --> PASS{All checks\npassed?}
    TEST --> PASS
    TYPE --> PASS
    PASS -->|No| BLOCK[Block merge]
    PASS -->|Yes| REVIEW[Code Review]
    REVIEW --> MERGE[Merge to main]
    MERGE --> DEPLOY[GitHub Actions\nDeploy Workflow]
    DEPLOY --> BUILD[Build Docker\nimage]
    BUILD --> RENDER[Deploy to Render\nautomatically]
    BUILD --> VERCEL[Deploy to Vercel\nautomatically]
```

```yaml
# .github/workflows/ci.yml
name: CI

on:
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: pip install -r backend/requirements.txt
      
      - name: Lint
        run: |
          ruff check backend/
          black --check backend/
      
      - name: Type check
        run: mypy backend/app
      
      - name: Test
        env:
          DATABASE_URL: sqlite:///./test.db
          REDIS_URL: redis://localhost:6379
        run: |
          pytest backend/tests/ -v --tb=short

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: {node-version: '20'}
      - run: cd frontend && npm ci
      - run: cd frontend && npm run type-check
      - run: cd frontend && npm run build
```

---

## 19. Claude ↔ Codex Handoff Protocol

### 19.1 Why This Exists

You'll use both Claude (for reasoning, architecture decisions, complex code) and Codex/GitHub Copilot (for implementation, debugging, iterating). When one is on cooldown, the other needs to pick up without losing context. This protocol makes that seamless.

```mermaid
sequenceDiagram
    participant YOU as You
    participant CL as Claude
    participant CX as Codex

    YOU->>CL: "Design the ABSA agent"
    CL->>CL: Reason, architect, write code
    CL->>YOU: Code + HANDOFF.md update
    Note over CL: Claude on cooldown

    YOU->>CX: "Implement what Claude designed"
    CX->>CX: Read HANDOFF.md + code
    CX->>CX: Implement, debug, run tests
    CX->>YOU: Implementation + PROGRESS.md update
    Note over CX: Codex done or stuck

    YOU->>CL: "Review what Codex built"
    CL->>CL: Read PROGRESS.md + code
    CL->>YOU: Review + next HANDOFF.md
```

### 19.2 The Three Handoff Files

**`PROGRESS.md`** — Always current. Shows exactly where we are.
```markdown
# VERA Progress Tracker

## Overall Status: PHASE 2 / 5

## ✅ Completed
- [x] Environment setup (§4)
- [x] Data download + filtering (§6)
- [x] Labeling run 1 (1000/2000 reviews)

## 🔄 In Progress
- [ ] Labeling run 2 (1000/2000 reviews) — notebook 02, cell 47
- [ ] Self-consistency check (notebook 03)

## ⏳ Not Started
- [ ] Fine-tuning (§12)
- [ ] Backend implementation (§14)
- [ ] Frontend (§16)
- [ ] Deployment (§17)

## Last Updated By: Claude | 2026-09-13 | Session #3
```

**`HANDOFF.md`** — Written at end of each working session.
```markdown
# Handoff to [Claude | Codex]

## What Was Done This Session
- Completed Agent 2 (ExperienceExtractor) — see backend/app/ml/agents/experience_extractor.py
- ONNX export works, model is at data/models/experience_model.onnx (90MB)
- Unit tests passing: pytest backend/tests/test_agents.py::TestExperienceExtractor

## Exact Next Steps for [Claude | Codex]
1. Implement Agent 3 (ABSA) — see §9 of PRD for exact code
2. Run: `python -c "from app.ml.agents.absa import ABSAModule; m = ABSAModule(); print(m.process('great sound but battery sucks'))"` 
3. Verify aspect detection works for all 10 aspects

## Blockers / Questions
- The ONNX export of deberta-v3-base-absa-v1.1 is tricky — model uses custom ops
  Suggestion: use PyABSA's built-in inference API instead of ONNX for ABSA agent
  
## Files Modified This Session
- backend/app/ml/agents/experience_extractor.py [NEW]
- backend/app/ml/models/loader.py [MODIFIED]
- backend/tests/test_agents.py [NEW]
- data/models/experience_model.onnx [NEW — 90MB]

## Environment State
- .venv active, all packages installed
- Colab notebook 04 completed, model pushed to HF Hub
- No uncommitted changes
```

**`DECISIONS.md`** — Immutable log of WHY decisions were made.
```markdown
# Architecture Decisions

## 2026-09-13: Use ONNX INT8 for production inference
**Decision:** Export DeBERTa to ONNX and quantize to INT8
**Why:** Render free tier has 512MB RAM. FP32 model is 730MB. INT8 is ~90MB.
**Trade-off:** ~2% accuracy loss on held-out set, acceptable given memory constraint.
**Alternative considered:** HuggingFace Inference API — rejected because free tier is rate-limited and adds network latency.

## 2026-09-13: Gemini Flash for labeling, not GPT-4o
**Decision:** Use Google Gemini 1.5 Flash for generating 2000 experience labels
**Why:** Completely free at our scale (1M tokens/day). GPT-4o at $0.05/label = $100 total.
**Risk:** Potentially lower quality than GPT-4o. Mitigated by: kappa > 0.70 gate before proceeding.
```

### 19.3 Claude's Role vs Codex's Role

| Task | Who Does It |
|---|---|
| Architectural decisions | **Claude** |
| Writing novel/complex algorithms (conformal calibration, EB) | **Claude** |
| Debugging logic errors or unexpected behavior | **Claude** |
| Boilerplate implementation (CRUD routes, DB migrations) | **Codex** |
| Running notebooks and iterating on hyperparameters | **Codex** |
| Writing tests for implemented code | **Codex** |
| CSS/Tailwind styling | **Codex** |
| Reviewing Codex-written code for correctness | **Claude** |

### 19.4 Session Start Protocol (Both Claude and Codex)

**Every session starts with:**
1. Read `PROGRESS.md` → know current state
2. Read `HANDOFF.md` → know exact next steps
3. Read `DECISIONS.md` → understand why things are built the way they are
4. Check `git log --oneline -5` → see recent changes

**Every session ends with:**
1. Update `PROGRESS.md` — mark completed items, update "In Progress"
2. Write new `HANDOFF.md` — be specific, include exact commands
3. Push all changes to git with descriptive commit message

---

## 20. Phased Roadmap

```mermaid
gantt
    title VERA Build Roadmap
    dateFormat  YYYY-MM-DD
    section Phase 1 — Data
    Environment setup           :done,    p1a, 2026-09-13, 2d
    Dataset download + filter   :done,    p1b, after p1a, 2d
    Label generation (2000)     :active,  p1c, after p1b, 3d
    Agreement measurement       :         p1d, after p1c, 2d

    section Phase 2 — Models
    Fine-tune DeBERTa (Colab)   :         p2a, after p1d, 2d
    ONNX export + quantize      :         p2b, after p2a, 1d
    Train domain rating model   :         p2c, after p1d, 1d
    Train XGBoost ensemble      :         p2d, after p2a, 2d
    Fit conformal calibrator    :         p2e, after p2d, 1d

    section Phase 3 — Backend
    FastAPI + DB schema         :         p3a, after p2e, 2d
    All 7 agents + pipeline     :         p3b, after p3a, 3d
    Celery worker + Redis       :         p3c, after p3b, 1d
    Unit + integration tests    :         p3d, after p3c, 2d

    section Phase 4 — Evaluation
    15-fold cross-validation    :         p4a, after p2e, 2d
    Ablation study              :         p4b, after p4a, 1d
    Calibration verification    :         p4c, after p4a, 1d
    Evaluation report           :         p4d, after p4c, 1d

    section Phase 5 — Frontend + Deploy
    Next.js frontend            :         p5a, after p3d, 3d
    Docker + Render deploy      :         p5b, after p5a, 1d
    Vercel frontend deploy      :         p5c, after p5b, 1d
    End-to-end demo test        :         p5d, after p5c, 1d
```

### 20.1 Decision Gates (Must Pass Before Proceeding)

| Gate | Condition to Pass |
|---|---|
| **G1: Labels ready** | Gemini self-consistency kappa > 0.70 AND human-Gemini kappa > 0.55 |
| **G2: Model ready** | Fine-tuned DeBERTa val MAE < 0.50 AND ONNX model produces same predictions as PyTorch (< 0.01 diff) |
| **G3: Pipeline ready** | All 7 agents produce output for 10 test reviews without errors; latency < 15s end-to-end on CPU |
| **G4: Eval passed** | VERA MAE < stars-only MAE with Wilcoxon p < 0.05 AND empirical coverage ≥ 88% for 90% target |
| **G5: Deploy ready** | /health returns 200, review submission returns result in < 30s, Render stays alive for 24h |

---

## 21. Weakness Resolution Matrix

Every known weakness has a concrete mitigation. Nothing is hand-waved.

| # | Weakness | Root Cause | Fix Applied | Verify |
|---|---|---|---|---|
| 1 | **Agent 1 torch/FastText RAM overflow** | SentenceTransformer (~350 MB PyTorch) + FastText (C++ native) loaded inside every review call; negates ONNX savings | Replaced with `langdetect` (pure Python, 1 MB) + sklearn TF-IDF cosine (no new model). Zero torch in production path. | `htop` inside Render container — peak RAM < 420 MB |
| 2 | **Celery product aggregation race** | Multiple reviews can finish concurrently while EB priors and rankings depend on the whole product population | One short global Redis aggregation lock (30 s TTL); a busy task retries after 12 s. Every published batch shares one prior and rank ordering. | Submit reviews for multiple ASINs simultaneously; all persisted products must share one consistent rank ordering. |
| 3 | **Empty product_asin bug** | `aggregate_product_task.delay('')` from reviews with no ASIN writes a corrupt `''` row and may call `redis.lock('')` | Guard: skip aggregation if `asin` is empty/whitespace after strip. `product_asin` in ReviewCreate may be optional but is sanitised before task dispatch. | Submit review with `product_asin=null`; confirm no `''` row in DB |
| 4 | **ABSA tokenizer argument order** | `tokenizer(aspect, text)` puts aspect first → review body gets truncated at position 0 of max_length window | Swapped to `tokenizer(text, aspect, max_length=512)`. Review body is always the first sequence; aspect is the second pair. | Compare sentiment scores for a 400-token review before/after fix — should differ |
| 5 | **EB variance underflow / one-review overconfidence** | Identical multi-review scores yield zero sample variance, while a single review cannot estimate its variance at all | Use a `0.05` variance floor for multi-review products and a conservative `0.5` minimum for one-review products. | Assert identical two-review products shrink, and a single 5.0 ranks below a well-supported 4.6 in the regression fixture. |
| 6 | **Domain model TF-IDF leakage** | TF-IDF vocabulary fitted on all 144K rows including test-split reviews → vocabulary leaks test signal into CV features | `DomainRatingModel.train()` now requires `held_out_asins` set. Rows with test ASINs are excluded before `fit_transform`. | Assert zero intersection between `safe_df['parent_asin']` and `test_df['parent_asin']` |
| 7 | **Upstash 10K command cap** | Default Celery polling at 0.1 s = 864K Redis commands/worker/day — 86× the free-tier limit | `polling_interval = 2.0` in `celery_app.conf`. Two workers = 86,400 poll commands + ~5 per review. `result_expires = 3600` auto-cleans tombstones. | Upstash dashboard: monitor daily command count after 24 h of normal use |
| 8 | **Render cold starts** | Free tier sleeps after 15 min inactivity | UptimeRobot pings `/health` every 5 min | Render logs: see pings, no 15+ min gaps |
| 9 | **torch in production image** | Importing transformers pulls in torch (~1.5 GB installed) | Strict split: `requirements.txt` (production) has only `onnxruntime` + `tokenizers`. `requirements-dev.txt` adds torch for Colab notebooks. | `pip list \| grep torch` inside Render container → empty |
| 10 | **Class imbalance** | 54.7% five-star in raw corpus | Stratified label sampling (400/star), class-weighted XGBoost | Verify label distribution print in notebook 02 |
| 11 | **Evaluation noise** | Only 2000 labels | 15-fold repeated CV + paired Wilcoxon, never single-split | Fold-std < 0.05 |
| 12 | **Leakage (train/test)** | Same product in both splits | Product-grouped splits throughout all CV + domain model training | Assert zero ASIN overlap |
| 13 | **No ground truth** | Stars are exactly what we distrust | Constructed labels + measured kappa + error vs noise floor | Section 13 evaluation protocol |
| 14 | **langdetect instability** | Throws `LangDetectException` on texts < 10 chars, emoji-only, or heavy punctuation — propagates up to Celery retry | Length guard (`< 10 chars → 'en'`) + broad `except Exception → 'en'` fallback. Never lets a language detection failure crash a review task. | Submit a review containing only `"👍👍👍"` — task should complete, not retry |
| 15 | **Conformal feature shift** | Optional API fields (`helpful_votes`, `verified_purchase`) default to `0`/`False`; production feature distribution narrows vs training, widening intervals incorrectly | (a) Training covers zero-metadata reviews (never filtered). (b) Missing fields filled with training-set means (stored in model pickle), not `0`. (c) Calibration set drawn from same distribution as production inputs — no quality filtering before calibration. | Compare interval widths for API-submitted reviews (no metadata) vs dataset reviews (full metadata) — widths should be within 15% | 
| 16 | **MAPIE / conformal serialization overhead** | Instantiating `MapieRegressor` at worker boot imports full sklearn dependency graph; re-fitting at runtime is wrong (leaks test data) | Offline: notebook 06 fits on held-out cal set and saves `q_hat` as a plain JSON float. Production: `ConformalPredictor` reads one float with `json.load()` — zero sklearn import, zero overhead. | `python -c "from app.ml.calibration.conformal import ConformalPredictor; p = ConformalPredictor(); print(p.q_hat)"` — must succeed without importing sklearn |

---

## 22. Success Criteria

### 22.1 Academic Criteria (Must All Pass)

The human-model agreement criterion below is **not met**: the available reference
annotations were produced by an LLM, not a human. Agreement with Claude may be
reported separately as reference-model agreement, but is not a substitute for
human validation. `human_validated` must remain `false` unless real human
annotations are collected and evaluated.

- [ ] VERA beats stars-only baseline (Wilcoxon p < 0.05) on 15-fold repeated product-grouped CV
- [ ] Reported MAE: mean ± std across folds, NOT a single-split number
- [ ] Fold win rate: VERA > stars-only in ≥ 85% of folds
- [ ] Empirical conformal coverage: ≥ 88% for 90% target (≥ 78% for 80% target)
- [ ] Label reliability: self-consistency kappa ≥ 0.70, human-model kappa ≥ 0.55
- [ ] Per-aspect detection F1 ≥ 0.70 for all 10 aspects
- [ ] Ablation: each retained component improves MAE in ≥ 60% of folds
- [ ] No leakage: assert zero ASIN overlap between train and test
- [ ] Negative results reported: if a component doesn't help, the paper says so

### 22.2 Production Criteria (Must All Pass)

Creating or deploying production resources requires explicit user approval. The current deployment
criteria are not verified; the backend target must first meet the FP32 worker's memory requirement.

- [ ] `/health` endpoint returns 200 always
- [ ] Review submission returns result in < 30 seconds (p95)
- [ ] Model inference: < 15 seconds end-to-end on CPU
- [ ] RAM usage: < 450 MB at peak
- [ ] Deployed to Render + Vercel (both public URLs work)
- [ ] No secrets in git history
- [ ] Alembic migrations apply cleanly from scratch
- [ ] All environment variables documented in `.env.example`
- [ ] Tests pass in CI (GitHub Actions green)

### 22.3 Demo Criteria

- [ ] Submit any earbud review → see corrected score + interval + aspects within 30 seconds
- [ ] Product ranking page loads with ≥ 10 products sorted by corrected score
- [ ] Star vs corrected score comparison is visually compelling (animation works)
- [ ] Aspect radar renders with correct sentiment colors
- [ ] UI works on mobile (responsive)

---

## 23. Implementation Corrections (v1.2)

Bugs, measured constraints, and implementation deviations found while building. Some gates still
depend on trained artifacts or an approved deployment target; rationale is in `DECISIONS.md`.
Where this table conflicts with earlier sections, **this table wins**.

| # | Area | v1.0 problem | v1.1 resolution |
|---|---|---|---|
| 1 | Environment | Pins (numpy 1.26.4, onnxruntime 1.19.0) have no wheels for Python ≥ 3.13 | Python 3.12 only |
| 2 | Requirements | MAPIE installed in production despite §10.3 | Moved to `requirements-dev.txt` |
| 3 | Tokenizer | `Tokenizer.from_pretrained` needs network and base DeBERTa has no `tokenizer.json`; fixed 512 padding; hardcoded pad id | Local `tokenizer.json`, dynamic padding, pad id from vocab, `only_first` pair truncation |
| 4 | ONNX feed | `token_type_ids` passed to graphs that do not declare it → onnxruntime error | Feed only declared inputs |
| 5 | Worker boot | `VERAPipeline()` at import time also loaded models inside the API | Lazy per-worker load; worker exits if artifacts missing |
| 6 | Agent 1 | `has_url` always False; `<br/>` glued words; substring keyword hits ("anc" in "balance") | Raw-text URL check, break tags → space, word boundaries |
| 7 | Agent 2 | Title prepended at inference only (train/serve skew) | Shared `format_experience_input` |
| 8 | Agent 3 | Softmax overflow; 10 separate ONNX calls; hardcoded label order | Stable softmax, one batch, `absa_config.json` |
| 9 | Agent 5 | Self-referencing formula; wrong half-life; freshness > 1 for future dates; hardcoded imputation | Weighted average, `0.5**(age/730)`, clip, means from artifact |
| 10 | Features | `imputation` argument unused | Imputation in Agent 5; features shared via `app/ml/features.py` |
| 11 | Fusion | `eval_set` on training data; pickle artifact | Removed; JSON artifact with feature-name check |
| 12 | Conformal | Interpolated / invalid quantile; constant-width intervals | Exact finite-sample rank; normalized method |
| 13 | EB prior | τ² = variance of all review scores | Method-of-moments between-product variance |
| 14 | EB uncertainty | Ad-hoc formula; τ² used as σ² for n = 1 | Posterior sd; pooled within-product variance |
| 15 | Tasks | Commit-then-enqueue could lose jobs; `failed` set while retrying; `review` may be None | Transactional outbox (`jobs`), durable retries, dispatcher thread |
| 16 | Schema | FK violation on first review of a new ASIN | Product shell created on submit |
| 17 | Leakage | Fusion trained on in-sample Agent 2 predictions | 5-fold product-grouped cross-fitting (out-of-fold scores) |
| 18 | Feature shift | Calibration metadata ≠ API metadata | Metadata dropout 0.5 (train) / 1.0 (calibration, test) |
| 19 | Domain model | Only test ASINs excluded; `stop_words_` bloat; numpy-2 pickles unloadable | Exclude all labelled ASINs; drop attribute; train in pinned env, version check |
| 20 | CV | `RepeatedGroupKFold` does not exist | 5 × 3 custom product-grouped folds |
| 21 | Corpus prep | Running langdetect on ~200K reviews (~1 h) just to clean text | `TextPreprocessor.clean_text` |
| 22 | Labeling | Gemini 1.5 Flash retired; current label runs use Groq | Current provider/model configuration is Groq (`gpt-oss-120b` + Qwen); Gemini remains legacy support only |
| 23 | Render | Render DB contradicts Supabase; free workers do not exist | Supabase remains the DB; free 512 MB Render plan is not suitable for the FP32 worker; deployment target requires user approval |
| 24 | CI | Lint tools not installed; `npm run type-check` script missing | Installed; `typecheck`; migration round-trip |
| 25 | Frontend | Next 14 end-of-life; shadcn CLI targets newer stacks | Next 16 / React 19, TS 6, ESLint 9, custom components |
| 26 | Upstash budget | 2 s polling = ~43K commands/day per worker > 10K free quota | Single worker, results ignored; expect paid Upstash or local Redis for sustained use |
| 27 | Label validation | The original protocol requires human-model agreement, but no human annotations were obtained | The 200 blinded reference annotations are Claude-generated and are explicitly non-human (`human_validated: false`). Agreement with this reference is a separate diagnostic and cannot satisfy the human-model criterion in §22.1. | Keep the human-model criterion unmet until genuine human annotations exist; do not present LLM-reference agreement as human validation. |
| 28 | Runtime memory | PRD assumes quantized models fit a 512 MB Render service | Quantized DeBERTa failed the export gate; production uses FP32 artifacts. A worker deployment requires at least 2 GiB as a starting allocation and a measured peak-RSS check. The 512 MB free Render plan is not a production target. | Verify with the complete artifact set before selecting a deployment target. Deployment resources require explicit user approval. |
| 29 | Agreement report schema | The legacy `human_agreement` field could describe agreement with a non-human reference | Name reference comparisons `reference_agreement`; keep `human_validated: false`. Legacy reports must not be relabeled as human evidence. | Regenerate reports from frozen checkpoint inputs when schema changes; never edit active labeling checkpoints to update report wording. |

---

## Appendix A: Quick Command Reference

```bash
# === LOCAL DEV ===
# Start backend
cd backend && uvicorn app.main:app --reload --port 8000

# Start worker
cd backend && celery -A app.worker.celery_app worker --loglevel=debug

# Start frontend
cd frontend && npm run dev

# Run tests
cd backend && pytest tests/ -v

# Apply DB migrations
cd backend && alembic upgrade head

# Create new migration
cd backend && alembic revision --autogenerate -m "description"

# === DOCKER ===
# Start postgres + redis locally
docker compose up -d

# === MODELS ===
# Download ONNX models from HF Hub
python backend/app/ml/models/loader.py

# === LABELS ===
# Run labeling (requires GEMINI_API_KEY)
jupyter nbconvert --to notebook --execute notebooks/02_label_generation.ipynb

# === EVALUATION ===
# Run full evaluation suite
jupyter nbconvert --to notebook --execute notebooks/08_evaluation_report.ipynb
```

---

## Appendix B: `.env.example`

```bash
# Copy to .env and fill in real values

DATABASE_URL=postgresql://user:password@host:5432/vera
SUPABASE_URL=https://YOURPROJECT.supabase.co
SUPABASE_ANON_KEY=your_anon_key_here

REDIS_URL=rediss://default:password@host.upstash.io:6379

GEMINI_API_KEY=your_google_ai_studio_key
GROQ_API_KEY=your_groq_key

HF_TOKEN=hf_your_token_here

SECRET_KEY=generate_with_python_-c_"import_secrets;print(secrets.token_hex(32))"
ENVIRONMENT=development

CORS_ORIGINS=http://localhost:3000
CELERY_BROKER_URL=${REDIS_URL}
CELERY_RESULT_BACKEND=${REDIS_URL}
```

---

*This PRD is the single source of truth for VERA. Every code file, notebook, and design decision traces back to a section here. When in doubt, re-read the relevant section. When something is wrong, update this document first.*

**Last updated:** 2026-09-14 | **Version:** 1.2.0 | **Status:** IN BUILD — see §23 for corrections
