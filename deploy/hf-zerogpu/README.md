---
title: VERA API
colorFrom: blue
colorTo: gray
sdk: gradio
sdk_version: 5.49.1
python_version: "3.12"
app_file: app.py
suggested_hardware: zero-a10g
pinned: false
short_description: VERA earbud review analysis API (FastAPI + Celery worker)
---

# VERA API (Hugging Face Space)

Backend for the VERA review analyzer. `app.py` starts loopback Redis, applies database
migrations, starts one Celery worker (which downloads the models from the private
`HF_MODEL_REPO`), and serves the FastAPI app on port 7860.

Endpoints: `GET /health`, `GET /ready`, `POST /api/reviews`, `GET /api/reviews/{id}`,
`GET /api/reviews/{id}/status`, `GET /api/products`, `GET /api/products/{asin}`.

Secrets (Settings -> Variables and secrets): `DATABASE_URL` (Supabase session pooler,
`?sslmode=require`), `HF_MODEL_REPO`, `HF_TOKEN` (read), `SECRET_KEY`, `CORS_ORIGINS`.
