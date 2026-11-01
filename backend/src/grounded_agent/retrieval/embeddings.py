from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from grounded_agent.retrieval.base import Vector


def _normalise(m: Vector) -> Vector:
    norms = np.linalg.norm(m, axis=-1, keepdims=True)
    return (m / np.clip(norms, 1e-12, None)).astype(np.float32)


class FastEmbedEmbedder:
    """Local ONNX embeddings (no API key). The model loads on first use, not at import."""

    def __init__(self, model_name: str, cache_dir: Path) -> None:
        self.model_name = model_name
        self._cache_dir = cache_dir
        self._model: Any = None

    def _get_model(self) -> Any:
        if self._model is None:
            from fastembed import TextEmbedding

            self._model = TextEmbedding(model_name=self.model_name, cache_dir=str(self._cache_dir))
        return self._model

    def embed_documents(self, texts: list[str]) -> Vector:
        return _normalise(np.array(list(self._get_model().passage_embed(texts)), dtype=np.float32))

    def embed_query(self, text: str) -> Vector:
        return _normalise(
            np.array(next(iter(self._get_model().query_embed(text))), dtype=np.float32)
        )
