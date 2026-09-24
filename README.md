# Signal

A personal information intelligence platform: ingest what you already care about, cluster duplicates, rank against your interest profile, and brief you with cited summaries.

This repository is a **modular monolith** (FastAPI + Next.js + PostgreSQL + Redis). Week 1 is accounts, a curated interest taxonomy, and onboarding. The feed pipeline starts in week 2.

## What works now

- Register / sign in with httpOnly JWT cookies
- Pick at least 5 interests from AI, Gaming, and Anime / Manga
- Health checks, Alembic migrations, topic seed, GitHub Actions CI

## Quick start (local)

You need Python 3.12 and Node 22. Docker is optional in week 1 (Postgres + Redis). Without Docker, the API can run on SQLite.

```bash
cp .env.example .env
docker compose up postgres redis -d

cd apps/api
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -e ".[dev]"
# Postgres (Compose running):
alembic upgrade head
python -m app.db.seed
uvicorn app.main:app --reload --port 8000

# Or SQLite, no Docker:
#   set DATABASE_URL=sqlite+aiosqlite:///./signal.db
#   uvicorn app.main:app --reload --port 8000
```

In another terminal:

```bash
cd apps/web
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). API docs: [http://localhost:8000/docs](http://localhost:8000/docs).

### Full stack via Compose

```bash
docker compose up --build
```

The browser still calls the API at `http://localhost:8000` (not the Docker-internal hostname).

## Tests

```bash
cd apps/api && pytest && ruff check .
cd apps/web && npm run lint
```

API tests use an in-memory SQLite database and do not require Docker.

## Repository layout

```
apps/api     FastAPI, Alembic, ARQ worker stub
apps/web     Next.js App Router
evals/       Golden sets (later)
fixtures/    Recorded feeds for ingest tests (later)
```

## What this is not (yet)

Not a chatbot, not an RSS reader UI, not eight source integrations, and not an agent swarm. See the project plan for the week-by-week path to a real morning brief.
