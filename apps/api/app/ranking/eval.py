"""Score topic relevance and feedback similarity against labeled (topic, headline) pairs.

    python -m app.ranking.eval ../../evals/relevance/pairs.jsonl

Curated topics use the aliases from the seed; custom topics use `aliases.json` next to the
pairs file, standing in for aliases a user would add themselves.
"""

import json
import sys
import uuid
from pathlib import Path

import numpy as np

from app.clustering.embedder import get_embedder
from app.core.config import settings
from app.core.tls import use_system_trust_store
from app.db.seed import ALIASES, TOPICS
from app.ranking.scoring import TopicProfile, match_topics, mentions


def _report(label: str, labels: np.ndarray, predicted: np.ndarray) -> None:
    true_pos = int(np.sum(predicted & labels))
    false_pos = int(np.sum(predicted & ~labels))
    precision = true_pos / max(true_pos + false_pos, 1)
    recall = true_pos / max(int(np.sum(labels)), 1)
    print(f"{label:>36}  precision={precision:.2f}  recall={recall:.2f}  false_pos={false_pos}")


def _aliases(path: Path) -> dict[str, list[str]]:
    by_name = {name: ALIASES.get(slug, []) for slug, name, _, _ in TOPICS}
    custom = path.parent / "aliases.json"
    if custom.exists():
        by_name.update(json.loads(custom.read_text(encoding="utf-8")))
    return by_name


def main(path: Path) -> None:
    pairs = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    aliases = _aliases(path)
    embedder = get_embedder()
    topics = embedder.embed([p["topic"] for p in pairs])
    headlines = embedder.embed([p["headline"] for p in pairs])
    similarity = np.sum(topics * headlines, axis=1)
    labels = np.array([bool(p["relevant"]) for p in pairs])
    named = np.array([mentions(p["topic"], p["headline"]) for p in pairs])
    aliased = np.array(
        [any(mentions(a, p["headline"]) for a in aliases.get(p["topic"], [])) for p in pairs]
    )
    current = settings.relevance_similarity_threshold

    print(f"model={embedder.model_name} pairs={len(pairs)} relevant={int(labels.sum())}\n")
    _report("mentions only", labels, named)
    _report("mentions + aliases", labels, named | aliased)
    _report(f"mentions + semantic>={current:.2f}", labels, named | (similarity >= current))
    for threshold in np.arange(0.56, 0.75, 0.02):
        _report(
            f"mentions + aliases + semantic>={threshold:.2f}",
            labels,
            named | aliased | (similarity >= threshold),
        )

    print(f"\nMistakes with aliases at RELEVANCE_SIMILARITY_THRESHOLD={current}:")
    for pair, topic_vec, headline_vec, label in zip(pairs, topics, headlines, labels, strict=True):
        profile = TopicProfile(
            uuid.uuid4(), pair["topic"], 1.0, topic_vec, tuple(aliases.get(pair["topic"], []))
        )
        matched = bool(match_topics(pair["headline"], headline_vec, [profile], current))
        if matched != label:
            kind = "missed" if label else "false match"
            score = float(topic_vec @ headline_vec)
            print(f"  [{kind}] {score:.3f}  {pair['topic']!r}: {pair['headline']!r}")

    _feedback(pairs, headlines, labels, named | aliased | (similarity >= current))


def _feedback(
    pairs: list[dict], headlines: np.ndarray, labels: np.ndarray, baseline: np.ndarray
) -> None:
    """Simulate one thumbs-up per topic (its first relevant headline) and measure what else
    the "close to a story you liked" rule pulls in, across every headline in the set."""
    liked: dict[str, int] = {}
    for index, pair in enumerate(pairs):
        if pair["relevant"]:
            liked.setdefault(pair["topic"], index)

    liked_rows = set(liked.values())
    print(f"\nFeedback: one liked headline for each of {len(liked)} topics")
    print("  recovered = relevant same-topic headlines the baseline missed, now pulled in")
    print("  wrong = irrelevant same-topic headlines pulled in")
    print("  other = headlines labeled under a different topic pulled in (likely unwanted)")
    for threshold in np.arange(0.50, 0.91, 0.05):
        recovered = wrong = other = 0
        for i, pair in enumerate(pairs):
            if i in liked_rows:
                continue
            for topic, j in liked.items():
                if float(headlines[j] @ headlines[i]) < threshold:
                    continue
                if pair["topic"] != topic:
                    other += 1
                elif not labels[i]:
                    wrong += 1
                elif not baseline[i]:
                    recovered += 1
        print(f"  liked>={threshold:.2f}  recovered={recovered}  wrong={wrong}  other={other}")
    print(f"FEEDBACK_SIMILARITY_THRESHOLD={settings.feedback_similarity_threshold}")


if __name__ == "__main__":
    use_system_trust_store()
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "../../evals/relevance/pairs.jsonl"))
