import hashlib
import re
from functools import lru_cache
from typing import Protocol

import numpy as np

from app.core.config import settings

_TOKEN = re.compile(r"[a-z0-9]+")


class Embedder(Protocol):
    model_name: str
    dim: int

    def embed(self, texts: list[str]) -> np.ndarray:
        """Return an (n, dim) float32 matrix of L2-normalized rows."""
        ...


def _normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (matrix / norms).astype(np.float32)


def embedding_text(title: str, content: str) -> str:
    # Headlines carry most of the "same event" signal; long bodies dilute it.
    return f"{title}\n{content[:500]}".strip()


class HashingEmbedder:
    """Bag-of-words feature hashing. Deterministic and offline; not semantic."""

    def __init__(self, dim: int) -> None:
        self.dim = dim
        self.model_name = f"hashing-{dim}"

    def embed(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            for token in _TOKEN.findall(text.lower()):
                value = int.from_bytes(hashlib.blake2b(token.encode(), digest_size=8).digest())
                out[row, value % self.dim] += 1.0 if value >> 63 else -1.0
        return _normalize(out)


class FastEmbedEmbedder:
    def __init__(self, model_name: str, dim: int) -> None:
        from fastembed import TextEmbedding

        self.model_name = model_name
        self.dim = dim
        self._model = TextEmbedding(model_name)

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        matrix = np.asarray(list(self._model.embed(texts)), dtype=np.float32)
        if matrix.shape[1] != self.dim:
            raise ValueError(
                f"{self.model_name} returned {matrix.shape[1]} dims; EMBEDDING_DIM is {self.dim}"
            )
        return _normalize(matrix)


@lru_cache
def get_embedder() -> Embedder:
    if settings.embedding_provider == "hashing":
        return HashingEmbedder(settings.embedding_dim)
    if settings.embedding_provider == "fastembed":
        return FastEmbedEmbedder(settings.embedding_model, settings.embedding_dim)
    raise ValueError(f"Unknown EMBEDDING_PROVIDER: {settings.embedding_provider}")
