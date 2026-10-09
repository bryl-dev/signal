"""Score the story-similarity threshold against labeled headline pairs.

    python -m app.clustering.eval ../../evals/dedup/pairs.jsonl
"""

import json
import sys
from pathlib import Path

import numpy as np

from app.clustering.embedder import embedding_text, get_embedder
from app.core.config import settings
from app.core.tls import use_system_trust_store


def _scores(labels: np.ndarray, predicted: np.ndarray) -> tuple[float, float, float]:
    true_pos = int(np.sum(predicted & labels))
    precision = true_pos / max(int(np.sum(predicted)), 1)
    recall = true_pos / max(int(np.sum(labels)), 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-9)
    return precision, recall, f1


def main(path: Path) -> None:
    pairs = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    embedder = get_embedder()
    left = embedder.embed([embedding_text(p["a"], p.get("a_text", "")) for p in pairs])
    right = embedder.embed([embedding_text(p["b"], p.get("b_text", "")) for p in pairs])
    similarity = np.sum(left * right, axis=1)
    labels = np.array([bool(p["same"]) for p in pairs])

    print(f"model={embedder.model_name} pairs={len(pairs)} positives={int(labels.sum())}\n")
    print("threshold  precision  recall  f1")
    for threshold in np.arange(0.76, 0.97, 0.02):
        precision, recall, f1 = _scores(labels, similarity >= threshold)
        print(f"{threshold:9.2f}  {precision:9.2f}  {recall:6.2f}  {f1:4.2f}")

    current = settings.cluster_similarity_threshold
    print(f"\nMistakes at CLUSTER_SIMILARITY_THRESHOLD={current}:")
    for pair, score, label in zip(pairs, similarity, labels, strict=True):
        if (score >= current) != label:
            kind = "missed duplicate" if label else "false merge"
            print(f"  [{kind}] {score:.3f}  {pair['a']!r} vs {pair['b']!r}")


if __name__ == "__main__":
    use_system_trust_store()
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "../../evals/dedup/pairs.jsonl"))
