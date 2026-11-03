"""Idempotent topic taxonomy seed. Safe to run on every API boot."""

from __future__ import annotations

import asyncio
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal
from app.db.sources_seed import seed_sources
from app.models.topic import Topic

# Stable UUIDs so fixtures and frontend snapshots can pin IDs if needed.
_NS = uuid5(NAMESPACE_URL, "https://signal.local/topics")

CATEGORIES: list[tuple[str, str]] = [
    ("ai", "AI"),
    ("gaming", "Gaming"),
    ("anime", "Anime / Manga"),
]

TOPICS: list[tuple[str, str, str, str]] = [
    # slug, name, category, description
    ("ai-agents", "AI agents", "ai", "Autonomous and tool-using AI systems"),
    ("llms", "LLMs", "ai", "Large language models and foundations"),
    ("openai", "OpenAI", "ai", "OpenAI models, products, and research"),
    ("anthropic", "Anthropic", "ai", "Claude, Constitutional AI, and related work"),
    ("ai-coding", "AI coding", "ai", "Coding assistants and developer tools"),
    ("rag", "RAG", "ai", "Retrieval-augmented generation"),
    ("ai-research", "AI research", "ai", "Papers and research labs"),
    ("elden-ring", "Elden Ring", "gaming", "Elden Ring and FromSoftware"),
    ("pokemon", "Pokémon", "gaming", "Pokémon games, TCG, and news"),
    ("nintendo", "Nintendo", "gaming", "Nintendo platforms and first-party games"),
    ("game-development", "Game development", "gaming", "Engines, tools, and indie production"),
    ("one-piece", "One Piece", "anime", "One Piece manga, anime, and official news"),
    ("jujutsu-kaisen", "Jujutsu Kaisen", "anime", "Jujutsu Kaisen series updates"),
    ("new-releases", "New releases", "anime", "New anime and manga releases"),
]


# Names that unambiguously refer to the topic. Phrases of 3 characters or fewer match case-
# sensitively, so "GPT" won't fire on "gpt" in a URL slug. Avoid words with everyday meanings
# ("Unity", "Cursor", "Worlds"): a false match costs more trust than a missed one.
ALIASES: dict[str, list[str]] = {
    "ai-agents": ["AI agent", "agentic", "coding agent", "autonomous agents"],
    "llms": [
        "LLM",
        "large language model",
        "language model",
        "GPT",
        "Llama",
        "Mistral",
        "Qwen",
        "DeepSeek",
        "Gemini",
    ],
    "openai": ["ChatGPT", "GPT-5", "Sora", "Sam Altman"],
    "anthropic": ["Claude", "Dario Amodei"],
    "ai-coding": ["Copilot", "Claude Code", "vibe coding", "coding agent", "coding assistant"],
    "rag": ["retrieval-augmented", "retrieval augmented generation", "vector database"],
    "ai-research": ["arXiv", "NeurIPS", "ICML", "ICLR", "DeepMind"],
    "elden-ring": ["Nightreign", "FromSoftware", "Shadow of the Erdtree"],
    "pokemon": ["Pokemon", "Pikachu", "Game Freak"],
    "nintendo": ["Switch 2", "Nintendo Switch", "Zelda", "Super Mario"],
    "game-development": ["Unreal Engine", "Godot", "gamedev", "game dev", "Unity engine"],
    "one-piece": ["Luffy", "Eiichiro Oda"],
    "jujutsu-kaisen": ["JJK", "Gege Akutami", "Sukuna"],
}


def topic_id(slug: str) -> UUID:
    return uuid5(_NS, slug)


async def seed_topics(session: AsyncSession) -> int:
    created = 0
    for slug, name, category, description in TOPICS:
        aliases = ALIASES.get(slug, [])
        existing = (
            await session.execute(select(Topic).where(Topic.slug == slug))
        ).scalar_one_or_none()
        if existing is not None:
            if existing.aliases != aliases:
                existing.aliases = aliases
            continue
        session.add(
            Topic(
                id=topic_id(slug),
                slug=slug,
                name=name,
                category=category,
                description=description,
                aliases=aliases,
                sort_order=created,
            )
        )
        created += 1
    await session.commit()
    return created


async def main() -> None:
    async with SessionLocal() as session:
        topics = await seed_topics(session)
        sources = await seed_sources(session)
        print(f"Seeded {topics} new topics, {sources} new sources.")


if __name__ == "__main__":
    asyncio.run(main())
