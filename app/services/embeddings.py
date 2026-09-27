from collections.abc import Sequence
from typing import Protocol

import numpy as np

from app.domain import EMBEDDING_DIMENSION


class Embedder(Protocol):
    dimension: int

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, question: str) -> list[float]: ...


class E5Embedder:
    """Lazy local multilingual E5 encoder with normalized 384D output."""

    dimension = EMBEDDING_DIMENSION

    def __init__(self, model_name: str, device: str = "cpu") -> None:
        self.model_name = model_name
        self.device = device
        self._model = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name, device=self.device)
            get_dimension = getattr(
                self._model,
                "get_embedding_dimension",
                self._model.get_sentence_embedding_dimension,
            )
            dimension = get_dimension()
            if dimension != self.dimension:
                raise RuntimeError(f"dimension embedding attendue={self.dimension}, reçue={dimension}")
        return self._model

    def _encode(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = self.model.encode(
            list(texts),
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return np.asarray(vectors, dtype=np.float32).tolist()

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        return self._encode([f"passage: {text}" for text in texts])

    def embed_query(self, question: str) -> list[float]:
        return self._encode([f"query: {question}"])[0]


def normalized_vector(values: Sequence[float]) -> list[float]:
    vector = np.asarray(values, dtype=np.float32)
    if vector.shape != (EMBEDDING_DIMENSION,):
        raise ValueError(f"embedding doit avoir {EMBEDDING_DIMENSION} dimensions")
    norm = float(np.linalg.norm(vector))
    if norm == 0:
        raise ValueError("embedding nul interdit")
    return (vector / norm).tolist()
