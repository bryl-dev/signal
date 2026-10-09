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

### Fixed

- HTML entities in feed titles and summaries are decoded.
- Identical templated posts (weekly megathreads) no longer merge across weeks.
