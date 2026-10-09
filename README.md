# Signal

A personal information intelligence platform: ingest what you already care about, cluster duplicates, rank against your interest profile, and brief you with cited summaries.

This repository is a **modular monolith** (FastAPI + Next.js + PostgreSQL/pgvector + Redis). Week 3 groups same-event coverage from different sources into stories.

## What works now

- Register / sign in with httpOnly JWT cookies
- Pick at least 5 interests, including custom topics
- Ingest RSS, YouTube channel RSS, and Hacker News into `documents`
- Embed every document locally (`BAAI/bge-small-en-v1.5` via fastembed, stored in pgvector) and group near-duplicates into stories
- Fetch latest from the home page; the feed shows stories with "also covered by" (no ranking yet)
- Health checks, Alembic migrations, topic/source seed, GitHub Actions CI

## How story grouping works

Grouping is conservative on purpose: a leftover duplicate is a small annoyance, but merging two different events hides news. A document joins an existing story only if, within a 72-hour window, either

1. its body is identical to a member's (bodies under 200 characters don't count), or
2. its embedding's cosine similarity to the story's **first** document is at least `CLUSTER_SIMILARITY_THRESHOLD`.

Comparing against the first document instead of any member stops stories from drifting through a chain of slightly-similar items. Each membership records how it matched (`content_hash` or `embedding` plus the score), so the UI can say why two items were grouped.

The threshold is picked from a labeled set of headline pairs in `evals/dedup/pairs.jsonl`, including hard negatives such as "same game, different patch":

```bash
cd apps/api
python -m app.clustering.eval ../../evals/dedup/pairs.jsonl   # precision/recall per threshold
python -m app.clustering.rebuild                              # regroup after changing rules
```

With the current 28 pairs, every threshold from 0.84 to 0.88 has zero false merges; the default is 0.86.

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
# optional: python -m app.ingest.run
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

API tests use an in-memory SQLite database and a deterministic hashing embedder, so they need neither Docker nor a model download.

The first ingest downloads the embedding model (~130 MB) into the local cache. Python verifies TLS against the OS certificate store (`truststore`), so this also works behind HTTPS-inspecting corporate proxies.

## Repository layout

```
apps/api     FastAPI, Alembic, ingest adapters, ARQ worker
apps/web     Next.js App Router
evals/       Labeled sets for tuning (dedup pairs today)
fixtures/    Recorded RSS feeds for ingest tests
```

## What this is not (yet)

Not a chatbot, not an RSS reader UI, not eight source integrations, and not an agent swarm. See the project plan for the week-by-week path to a real morning brief.
