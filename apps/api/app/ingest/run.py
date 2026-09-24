"""Manual ingest: python -m app.ingest.run"""

import asyncio

from app.db.session import SessionLocal
from app.ingest.pipeline import ingest_all


async def main() -> None:
    async with SessionLocal() as session:
        summary = await ingest_all(session)
        print(summary)


if __name__ == "__main__":
    asyncio.run(main())
