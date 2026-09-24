from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source import Source

_NS = uuid5(NAMESPACE_URL, "https://signal.local/sources")

SOURCES: list[dict] = [
    {
        "slug": "hacker-news",
        "name": "Hacker News",
        "source_type": "hn",
        "homepage_url": "https://news.ycombinator.com",
        "quality_tier": "forum",
        "default_content_type": "discussion",
        "fetch_config": {
            "allowed_hosts": ["hacker-news.firebaseio.com"],
            "max_items": 20,
        },
    },
    {
        "slug": "ann",
        "name": "Anime News Network",
        "source_type": "rss",
        "homepage_url": "https://www.animenewsnetwork.com",
        "quality_tier": "major_news",
        "default_content_type": "news",
        "fetch_config": {
            "feed_url": "https://www.animenewsnetwork.com/all/rss.xml",
            "allowed_hosts": ["www.animenewsnetwork.com", "animenewsnetwork.com"],
            "max_items": 20,
        },
    },
    {
        "slug": "reddit-granblue-relink",
        "name": "r/GranblueFantasyRelink",
        "source_type": "rss",
        "homepage_url": "https://www.reddit.com/r/GranblueFantasyRelink/",
        "quality_tier": "forum",
        "default_content_type": "discussion",
        "fetch_config": {
            "feed_url": "https://www.reddit.com/r/GranblueFantasyRelink/.rss",
            "allowed_hosts": ["www.reddit.com", "reddit.com"],
            "max_items": 15,
        },
    },
    {
        "slug": "reddit-monster-hunter",
        "name": "r/MonsterHunter",
        "source_type": "rss",
        "homepage_url": "https://www.reddit.com/r/MonsterHunter/",
        "quality_tier": "forum",
        "default_content_type": "discussion",
        "fetch_config": {
            "feed_url": "https://www.reddit.com/r/MonsterHunter/.rss",
            "allowed_hosts": ["www.reddit.com", "reddit.com"],
            "max_items": 15,
        },
    },
    {
        "slug": "reddit-lol",
        "name": "r/leagueoflegends",
        "source_type": "rss",
        "homepage_url": "https://www.reddit.com/r/leagueoflegends/",
        "quality_tier": "forum",
        "default_content_type": "discussion",
        "fetch_config": {
            "feed_url": "https://www.reddit.com/r/leagueoflegends/.rss",
            "allowed_hosts": ["www.reddit.com", "reddit.com"],
            "max_items": 15,
        },
    },
    {
        "slug": "polygon",
        "name": "Polygon",
        "source_type": "rss",
        "homepage_url": "https://www.polygon.com",
        "quality_tier": "major_news",
        "default_content_type": "news",
        "fetch_config": {
            "feed_url": "https://www.polygon.com/rss/index.xml",
            "allowed_hosts": ["www.polygon.com", "polygon.com"],
            "max_items": 15,
        },
    },
]


def source_id(slug: str) -> UUID:
    return uuid5(_NS, slug)


async def seed_sources(session: AsyncSession) -> int:
    legacy = await session.execute(select(Source).where(Source.slug == "youtube-ign"))
    old_youtube = legacy.scalar_one_or_none()
    if old_youtube and old_youtube.is_enabled:
        old_youtube.is_enabled = False
        await session.commit()

    created = 0
    for row in SOURCES:
        existing = await session.execute(select(Source).where(Source.slug == row["slug"]))
        found = existing.scalar_one_or_none()
        if found is not None:
            continue
        session.add(
            Source(
                id=source_id(row["slug"]),
                name=row["name"],
                slug=row["slug"],
                source_type=row["source_type"],
                homepage_url=row["homepage_url"],
                fetch_config=row["fetch_config"],
                quality_tier=row["quality_tier"],
                default_content_type=row["default_content_type"],
                is_enabled=True,
            )
        )
        created += 1
    if created:
        await session.commit()
    return created
