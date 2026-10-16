"""Local multilingual sentence embeddings (free, no API).

EmbeddingGemma replaced paraphrase-multilingual-MiniLM on 2026-10-16: on hand-labelled Korean and English
headlines it picked the right seed topic 18/19 times against 12/19, and MiniLM's quantized ONNX build rated
unrelated Korean headlines 0.96 alike. It costs ~120 ms per item on CPU, a few seconds per daily run."""
from __future__ import annotations

from hub_collect.normalize import Item

MODEL_NAME = "google/embeddinggemma-300m"
DIM = 768  # stored as halfvec, so a row costs what a 384-dim float vector did


def embedding_text(item: Item) -> str:
    return f"{item.title}. {item.summary}" if item.summary else item.title


class Embedder:
    """Loads the model on first use so runs with nothing new skip the ~1.2GB download."""

    def __init__(self, cache_dir: str | None = None):
        self._cache_dir = cache_dir
        self._model = None

    def vectors(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            from fastembed import TextEmbedding  # heavy import kept out of unit tests

            self._model = TextEmbedding(MODEL_NAME, cache_dir=self._cache_dir)
        return [vector.tolist() for vector in self._model.embed(texts)]
