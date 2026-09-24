.PHONY: dev-infra api web test lint seed

dev-infra:
	docker compose up postgres redis -d

api:
	cd apps/api && uvicorn app.main:app --reload --port 8000

web:
	cd apps/web && npm run dev

seed:
	cd apps/api && python -m app.db.seed

test:
	cd apps/api && pytest
	cd apps/web && npm run lint

lint:
	cd apps/api && ruff check .
	cd apps/web && npm run lint
