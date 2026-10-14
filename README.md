# Signal

A personal information intelligence platform: ingest what you already care about, cluster duplicates, rank against your interest profile, and brief you with cited summaries.

This repository is a **modular monolith** (FastAPI + Next.js + PostgreSQL/pgvector + Redis). Week 3 groups same-event coverage from different sources into stories; week 4 ranks those stories against your interests and says why; week 5 turns the top stories into a morning brief where every line cites its sources.

## What works now

- Register / sign in with httpOnly JWT cookies
- Pick at least 5 interests, including custom topics
- Ingest RSS, YouTube channel RSS, and Hacker News into `documents`
- Embed every document locally (`BAAI/bge-small-en-v1.5` via fastembed, stored in pgvector) and group near-duplicates into stories
- A ranked "For you" feed: stories from the last 7 days that match your interests, each with the reasons it ranked where it did
- A morning brief: your top 8 stories summarized by a local model (Ollama), every bullet citing the articles it came from
- Sources: Hacker News, Anime News Network, Polygon, Steam News, and a few subreddits
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

## How the feed is ranked

A story is relevant to an interest if it **mentions** the interest by name (case- and punctuation-insensitive, whole words, so "Granblue Fantasy: Relink" matches but "anthropology" does not match "Anthropic"), or if its embedding is **related**: cosine similarity at least `RELEVANCE_SIMILARITY_THRESHOLD`. Unmatched stories go to "Everything else" instead of disappearing.

Matched stories are ordered by a linear score in which every feature is between 0 and 1:

| Feature | Weight | Value |
| --- | --- | --- |
| Relevance | 0.55 | interest weight × 1.0 for a mention, × 0.8 for a semantic match |
| Recency | 0.25 | halves every 24 hours |
| Coverage | 0.12 | 0 for one source, 0.5 for two, 1 for four or more |
| Source quality | 0.08 | by source tier (major news > aggregator > forum) |

The relevance threshold comes from `evals/relevance/pairs.jsonl` (`python -m app.ranking.eval`). On 40 labeled pairs, name mentions alone get precision 1.00 / recall 0.37; adding semantic matches at 0.64 gets 0.93 / 0.68. The remaining misses need world knowledge a small embedding model lacks (that "Claude" is Anthropic, or "Faker" is League of Legends), which is the next thing to fix — through topic aliases or feedback — rather than lowering the threshold.

## How the brief is written

The brief takes the top `BRIEF_SIZE` stories from the feed and summarizes each from at most four of its articles, numbered `[1]`–`[4]`. The model (default `qwen2.5:7b` through [Ollama](https://ollama.com), so it runs on a laptop GPU and costs nothing) must reply in a JSON schema: a headline plus one to three bullets, each with the source numbers it relies on. Article text is passed as untrusted data, and the prompt says so.

A schema guarantees shape, not truth, so the output is checked in code:

- a citation must point at a source that exists;
- every number in a bullet (counts, prices, dates, versions) must appear in a source it cites, and a headline with an unsupported number is replaced by the lead article's title;
- stories whose articles have no body text (link posts) skip the model entirely, since it would only invent context;
- bullets that fail are dropped; if none survive, the model gets one retry, and then the story falls back to the lead article's opening sentence, labeled as an excerpt.

If Ollama is down, the brief is still produced (all excerpts) instead of failing, and stops calling the server after the first connection error. Summaries are cached per story and reused until the story's set of articles changes. Each brief is saved as a snapshot, so a past brief reads the same even after stories are regrouped.

`evals/briefing/cases.jsonl` holds eight multi-source stories, including conflicting numbers and a prompt-injection attempt (`python -m app.briefing.eval`). With `qwen2.5:7b` on an RTX 4060 laptop GPU, the seven with article text pass validation on the first try (the eighth is a link post and correctly skips the model) with no injection leaks, at about 5 s per story once the model is loaded (the first call loads it into VRAM, which can take minutes). Validation catches invented numbers, not every wrong claim: the eval output still shows the model blending two disagreeing sales figures and adding mild editorial lines, which is why the brief links every claim back to its sources.

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

API tests use an in-memory SQLite database, a deterministic hashing embedder, and a fake LLM client, so they need neither Docker, Ollama, nor a model download.

The first ingest downloads the embedding model (~130 MB) into the local cache. Python verifies TLS against the OS certificate store (`truststore`), so this also works behind HTTPS-inspecting corporate proxies.

## Repository layout

```
apps/api     FastAPI, Alembic, ingest adapters, ARQ worker
apps/web     Next.js App Router
evals/       Labeled sets for tuning (dedup, relevance, briefing)
fixtures/    Recorded RSS feeds for ingest tests
```

## What this is not (yet)

Not a chatbot, not an RSS reader UI, not eight source integrations, and not an agent swarm. See the project plan for the week-by-week path to a real morning brief.
