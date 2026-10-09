"""Drop all stories and regroup every document (embeddings are kept).

Run after changing the threshold, window, or grouping rules:
    python -m app.clustering.rebuild
"""

import asyncio

from sqlalchemy import delete

from app.clustering.service import process_new_documents
from app.core.tls import use_system_trust_store
from app.db.session import SessionLocal
from app.models.story import Story, StoryMember


async def main() -> None:
    async with SessionLocal() as session:
        await session.execute(delete(StoryMember))
        await session.execute(delete(Story))
        await session.commit()
        print(await process_new_documents(session))


if __name__ == "__main__":
    use_system_trust_store()
    asyncio.run(main())
