# VERA Progress Tracker

## Overall Status: PHASE 3 (backend core) — in progress

## ✅ Completed
- [x] Environment setup (§4): venv (py3.12), prod + lint deps
- [x] Root config: .gitignore, .env.example, pyproject.toml, docker-compose.yml
- [x] Backend config, database, ORM models
- [x] ML agents 1–7, artifact loader, calibrated review pipeline, and EB aggregation
- [x] Pydantic schemas, FastAPI review/product/health routes
- [x] Celery worker/tasks with retry handling and race-safe aggregation
- [x] Alembic initial migration (verified from a clean SQLite database)
- [x] Backend tests, Ruff, Black, and mypy checks
- [x] `DECISIONS.md` and PRD corrections for aggregation behaviour

## ⏳ Not Started
- [ ] `training/vera_training` package (data, labeling, agreement, finetune, export, fusion, calibration, eval)
- [ ] Notebooks 01–08
- [ ] Frontend (Next.js 14)
- [ ] Dockerfile.backend, render.yaml, CI/CD workflows
- [ ] README, DECISIONS.md, PRD.md patches
- [ ] (USER) Supabase + Upstash credentials in `.env`
- [ ] (USER, Colab) Phase 1 data + labels, Phase 2 model training, upload artifacts to HF Hub

## Last Updated By: Codex | 2026-09-13 | Session #2
