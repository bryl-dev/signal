"""Explainable linear ranker. Every feature is in [0, 1] and every score is a weighted sum,
so the feed can show exactly why a story is where it is."""

import math
import re
import unicodedata
import uuid
from dataclasses import dataclass

import numpy as np

from app.core.config import settings

_NON_WORD = re.compile(r"[\W_]+")

# A semantic match is weaker evidence than the story naming the topic outright.
MENTION_STRENGTH = 1.0
SEMANTIC_STRENGTH = 0.8

QUALITY_BY_TIER = {
    "official": 1.0,
    "major_news": 0.9,
    "aggregator": 0.7,
    "blog": 0.6,
    "forum": 0.4,
}
DEFAULT_QUALITY = 0.5


@dataclass(frozen=True)
class TopicProfile:
    topic_id: uuid.UUID
    name: str
    weight: float
    vector: np.ndarray


@dataclass(frozen=True)
class TopicMatch:
    topic_id: uuid.UUID
    name: str
    kind: str  # "mention" or "semantic"
    similarity: float
    strength: float


@dataclass(frozen=True)
class Reason:
    kind: str
    label: str
    contribution: float


@dataclass(frozen=True)
class Ranked:
    score: float
    matches: list[TopicMatch]
    reasons: list[Reason]


def _normalize(text: str) -> str:
    folded = unicodedata.normalize("NFKC", text).casefold()
    return f" {_NON_WORD.sub(' ', folded).strip()} "


def mentions(topic_name: str, text: str) -> bool:
    """Whole-word, case- and punctuation-insensitive phrase match."""
    needle = _normalize(topic_name)
    return needle.strip() != "" and needle in _normalize(text)


def match_topics(
    text: str,
    vector: np.ndarray,
    topics: list[TopicProfile],
    threshold: float,
) -> list[TopicMatch]:
    matches = []
    for topic in topics:
        similarity = float(topic.vector @ vector)
        if mentions(topic.name, text):
            matches.append(
                TopicMatch(topic.topic_id, topic.name, "mention", similarity, MENTION_STRENGTH)
            )
        elif similarity >= threshold:
            matches.append(
                TopicMatch(topic.topic_id, topic.name, "semantic", similarity, SEMANTIC_STRENGTH)
            )
    return sorted(matches, key=lambda match: (-match.strength, -match.similarity))


def recency_score(age_hours: float, half_life_hours: float) -> float:
    return 0.5 ** (max(age_hours, 0.0) / half_life_hours)


def coverage_score(source_count: int) -> float:
    # 1 source -> 0, 2 -> 0.5, 4+ -> 1.
    return min(1.0, math.log2(max(source_count, 1)) / 2)


def quality_score(tiers: list[str]) -> float:
    return max((QUALITY_BY_TIER.get(tier, DEFAULT_QUALITY) for tier in tiers), default=0.0)


def _age_label(age_hours: float) -> str:
    if age_hours < 1:
        return "under an hour ago"
    if age_hours < 48:
        return f"{int(age_hours)}h ago"
    return f"{int(age_hours // 24)} days ago"


def rank(
    matches: list[TopicMatch],
    weights_by_topic: dict[uuid.UUID, float],
    age_hours: float,
    source_count: int,
    tiers: list[str],
) -> Ranked:
    relevance = max(
        (match.strength * weights_by_topic[match.topic_id] for match in matches), default=0.0
    )
    features = [
        ("relevance", settings.rank_weight_relevance, relevance),
        (
            "recency",
            settings.rank_weight_recency,
            recency_score(age_hours, settings.recency_half_life_hours),
        ),
        ("coverage", settings.rank_weight_coverage, coverage_score(source_count)),
        ("quality", settings.rank_weight_quality, quality_score(tiers)),
    ]

    reasons = []
    for match in matches:
        label = (
            f"Mentions {match.name}"
            if match.kind == "mention"
            else f"Related to {match.name} ({match.similarity:.2f})"
        )
        reasons.append(Reason("topic", label, 0.0))
    contributions = {name: weight * value for name, weight, value in features}
    if reasons:
        reasons[0] = Reason("topic", reasons[0].label, round(contributions["relevance"], 3))
    reasons.append(Reason("recency", _age_label(age_hours), round(contributions["recency"], 3)))
    if source_count > 1:
        reasons.append(
            Reason("coverage", f"{source_count} sources", round(contributions["coverage"], 3))
        )

    return Ranked(
        score=round(sum(contributions.values()), 4),
        matches=matches,
        reasons=reasons,
    )
