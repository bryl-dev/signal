"""Manual ingest + clustering: python -m app.ingest.run"""

import asyncio

from app.clustering.service import process_new_documents
from app.core.tls import use_system_trust_store
from app.db.session import SessionLocal
from app.ingest.pipeline import ingest_all


async def main() -> None:
    async with SessionLocal() as session:
        summary = await ingest_all(session)
        summary.update(await process_new_documents(session))
        print(summary)


if __name__ == "__main__":
    use_system_trust_store()
    asyncio.run(main())
