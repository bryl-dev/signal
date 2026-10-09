"""Score topic relevance matching against labeled (topic, headline) pairs.

    python -m app.ranking.eval ../../evals/relevance/pairs.jsonl
"""

import json
import sys
import uuid
from pathlib import Path

import numpy as np

from app.clustering.embedder import get_embedder
from app.core.config import settings
from app.core.tls import use_system_trust_store
from app.ranking.scoring import TopicProfile, match_topics, mentions


def _report(label: str, labels: np.ndarray, predicted: np.ndarray) -> None:
    true_pos = int(np.sum(predicted & labels))
    false_pos = int(np.sum(predicted & ~labels))
    precision = true_pos / max(true_pos + false_pos, 1)
    recall = true_pos / max(int(np.sum(labels)), 1)
    print(f"{label:>28}  precision={precision:.2f}  recall={recall:.2f}  false_pos={false_pos}")


def main(path: Path) -> None:
    pairs = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    embedder = get_embedder()
    topics = embedder.embed([p["topic"] for p in pairs])
    headlines = embedder.embed([p["headline"] for p in pairs])
    similarity = np.sum(topics * headlines, axis=1)
    named = np.array([mentions(p["topic"], p["headline"]) for p in pairs])
    labels = np.array([bool(p["relevant"]) for p in pairs])

    print(f"model={embedder.model_name} pairs={len(pairs)} relevant={int(labels.sum())}\n")
    _report("mentions only", labels, named)
    for threshold in np.arange(0.56, 0.75, 0.02):
        _report(f"mentions + semantic>={threshold:.2f}", labels, named | (similarity >= threshold))

    current = settings.relevance_similarity_threshold
    print(f"\nMistakes at RELEVANCE_SIMILARITY_THRESHOLD={current}:")
    for pair, topic_vec, headline_vec, label in zip(pairs, topics, headlines, labels, strict=True):
        profile = TopicProfile(uuid.uuid4(), pair["topic"], 1.0, topic_vec)
        matched = bool(match_topics(pair["headline"], headline_vec, [profile], current))
        if matched != label:
            kind = "missed" if label else "false match"
            score = float(topic_vec @ headline_vec)
            print(f"  [{kind}] {score:.3f}  {pair['topic']!r}: {pair['headline']!r}")


if __name__ == "__main__":
    use_system_trust_store()
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "../../evals/relevance/pairs.jsonl"))
