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
# Being close to a story you liked is evidence of interest even without a topic match.
LIKED_STRENGTH = 0.7
# Being close to a story you hid halves relevance rather than hiding it outright.
DISLIKED_FACTOR = 0.5
# Short phrases such as "LoL", "GPT", or "RAG" collide with ordinary words when case is ignored.
CASE_SENSITIVE_MAX_CHARS = 3

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
    aliases: tuple[str, ...] = ()
    # Net thumbs up minus down on stories that matched this topic.
    votes: int = 0


@dataclass(frozen=True)
class TopicMatch:
    topic_id: uuid.UUID
    name: str
    kind: str  # "mention" or "semantic"
    similarity: float
    strength: float
    # The alias that was mentioned, when it wasn't the topic name itself.
    via: str | None = None


@dataclass(frozen=True)
class FeedbackSignal:
    """The closest story the user voted on. `title` is None when it is this story."""

    title: str | None
    similarity: float


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


def _normalize(text: str, fold_case: bool = True) -> str:
    text = unicodedata.normalize("NFKC", text)
    if fold_case:
        text = text.casefold()
    return f" {_NON_WORD.sub(' ', text).strip()} "


def mentions(phrase: str, text: str) -> bool:
    """Whole-word, punctuation-insensitive phrase match; case-insensitive unless very short."""
    fold_case = len(phrase.strip()) > CASE_SENSITIVE_MAX_CHARS
    needle = _normalize(phrase, fold_case)
    return needle.strip() != "" and needle in _normalize(text, fold_case)


def match_topics(
    text: str,
    vector: np.ndarray,
    topics: list[TopicProfile],
    threshold: float,
) -> list[TopicMatch]:
    matches = []
    for topic in topics:
        similarity = float(topic.vector @ vector)
        phrase = next(
            (phrase for phrase in (topic.name, *topic.aliases) if mentions(phrase, text)), None
        )
        if phrase is not None:
            via = None if phrase == topic.name else phrase
            matches.append(
                TopicMatch(
                    topic.topic_id, topic.name, "mention", similarity, MENTION_STRENGTH, via
                )
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


def _topic_label(match: TopicMatch) -> str:
    if match.kind == "semantic":
        return f"Related to {match.name} ({match.similarity:.2f})"
    if match.via:
        return f"Mentions {match.via} ({match.name})"
    return f"Mentions {match.name}"


def _quote(title: str, limit: int = 60) -> str:
    return f"“{title if len(title) <= limit else title[: limit - 1].rstrip() + '…'}”"


def rank(
    matches: list[TopicMatch],
    weights_by_topic: dict[uuid.UUID, float],
    age_hours: float,
    source_count: int,
    tiers: list[str],
    liked: FeedbackSignal | None = None,
    disliked: FeedbackSignal | None = None,
    votes_by_topic: dict[uuid.UUID, int] | None = None,
) -> Ranked:
    topic_relevance = max(
        (match.strength * weights_by_topic[match.topic_id] for match in matches), default=0.0
    )
    liked_relevance = LIKED_STRENGTH if liked else 0.0
    unpenalized = max(topic_relevance, liked_relevance)
    relevance = unpenalized * DISLIKED_FACTOR if disliked else unpenalized
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

    contributions = {name: weight * value for name, weight, value in features}
    driver = round(settings.rank_weight_relevance * unpenalized, 3)
    liked_drives = liked_relevance > topic_relevance

    reasons = []
    if liked:
        label = (
            "You liked this"
            if liked.title is None
            else f"Like {_quote(liked.title)}, which you liked"
        )
        reasons.append(Reason("feedback", label, driver if liked_drives else 0.0))
    for index, match in enumerate(matches):
        contribution = driver if index == 0 and not liked_drives else 0.0
        reasons.append(Reason("topic", _topic_label(match), contribution))
    if matches and not liked_drives:
        # Topic matches lead so the main reason reads first.
        reasons.sort(key=lambda reason: reason.kind != "topic")
        votes = (votes_by_topic or {}).get(matches[0].topic_id, 0)
        if votes:
            verb = "Boosted" if votes > 0 else "Lowered"
            reasons.append(Reason("feedback", f"{verb} by your votes on {matches[0].name}", 0.0))
    if disliked:
        penalty = round(contributions["relevance"] - driver, 3)
        reasons.append(
            Reason("feedback", f"Similar to {_quote(disliked.title or '')}, which you hid", penalty)
        )
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
