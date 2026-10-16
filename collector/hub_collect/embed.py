"""Local multilingual sentence embeddings (free, no API)."""
from __future__ import annotations

from hub_collect.normalize import Item

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DIM = 384


def embedding_text(item: Item) -> str:
    return f"{item.title}. {item.summary}" if item.summary else item.title


class Embedder:
    """Loads the model on first use so runs with nothing new skip the ~200MB download."""

    def __init__(self, cache_dir: str | None = None):
        self._cache_dir = cache_dir
        self._model = None

    def vectors(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            from fastembed import TextEmbedding  # heavy import kept out of unit tests

            self._model = TextEmbedding(MODEL_NAME, cache_dir=self._cache_dir)
        return [vector.tolist() for vector in self._model.embed(texts)]
