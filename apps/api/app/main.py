import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.base import Base
from app.db.seed import seed_topics
from app.db.session import SessionLocal, engine
from app.db.sources_seed import seed_sources
from app.models import Document, IngestionRun, Source, Topic, User, UserInterest  # noqa: F401

configure_logging()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.is_sqlite:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    try:
        async with SessionLocal() as session:
            created = await seed_topics(session)
            if created:
                logger.info("topics_seeded", count=created)
            sources = await seed_sources(session)
            if sources:
                logger.info("sources_seeded", count=sources)
    except Exception:
        # Fresh test databases create tables after app init; seed is best-effort.
        logger.warning("topic_seed_skipped", exc_info=True)
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id, path=request.url.path)
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response


app.include_router(api_router, prefix="/v1")


@app.get("/health")
async def health_root() -> dict[str, str]:
    return {"status": "ok", "service": "signal-api"}


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "signal-api", "docs": "/docs"}
