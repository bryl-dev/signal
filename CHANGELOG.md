# Changelog

All notable changes to Signal are documented here.

## [0.1.0] - Unreleased

### Added

- Monorepo scaffold (FastAPI API, Next.js web, Docker Compose).
- Email/password auth with httpOnly JWT cookies.
- Curated interest taxonomy and onboarding (AI, Gaming, Anime / Manga).
- Health endpoint, Alembic migrations, GitHub Actions CI.
- Source adapters (RSS, YouTube RSS, Hacker News) and document ingest.
- Local embeddings in pgvector and conservative story grouping (identical text, then
  embedding similarity to the story's first document, within 72 hours).
- `GET /v1/stories`, a dedup eval set with a threshold-sweep script, and a rebuild command.
- Steam News as a gaming source.
- `GET /v1/feed`: explainable linear ranking of recent stories against the user's interests
  (name mentions plus semantic similarity), with a labeled relevance eval set.
- Cited morning brief (`POST /v1/brief`, `GET /v1/brief`, `/brief` page): top stories summarized
  by a local model through Ollama, with citation and number checks, an extractive fallback,
  per-story summary caching, saved brief snapshots, and a summarization eval.
- Topic aliases (curated, plus per-user via `PATCH /v1/me/interests/{topic_id}`); short aliases
  match case-sensitively. Relevance recall on the eval set rises from 0.68 to 0.84.
- Story feedback (`PUT /v1/feedback`): thumbs-down hides a story and demotes near-duplicates,
  votes adjust topic weights, and close follow-ups to liked stories join the feed.

### Changed

- Re-saving interests keeps existing interests' weights and aliases instead of recreating them.

### Fixed

- HTML entities in feed titles and summaries are decoded.
- Identical templated posts (weekly megathreads) no longer merge across weeks.
