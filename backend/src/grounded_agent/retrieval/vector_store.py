"""Exact cosine search over an in-memory matrix, persisted to disk by corpus fingerprint.

At ~40 chunks a vector database is overhead; the VectorStore protocol is the seam where
Qdrant/pgvector would plug in (docs/scaling.md).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from grounded_agent.domain.policy import PolicyChunk
from grounded_agent.retrieval.base import Embedder, Vector


def corpus_fingerprint(chunks: list[PolicyChunk], model_name: str) -> str:
    h = hashlib.sha256(model_name.encode())
    for c in chunks:
        h.update(c.chunk_id.encode())
        h.update(c.embedding_text().encode())
    return h.hexdigest()[:16]


class NumpyVectorStore:
    def __init__(self, matrix: Vector) -> None:
        self._matrix = matrix

    @classmethod
    def build(
        cls, chunks: list[PolicyChunk], embedder: Embedder, cache_dir: Path | None
    ) -> NumpyVectorStore:
        """Load cached vectors when the corpus and model are unchanged, else embed and save."""
        fingerprint = corpus_fingerprint(chunks, embedder.model_name)
        index_dir = cache_dir / "index" / fingerprint if cache_dir else None
        if index_dir and (index_dir / "vectors.npy").exists():
            return cls(np.load(index_dir / "vectors.npy"))

        matrix = embedder.embed_documents([c.embedding_text() for c in chunks])
        if index_dir:
            index_dir.mkdir(parents=True, exist_ok=True)
            np.save(index_dir / "vectors.npy", matrix)
            manifest = {"model": embedder.model_name, "chunk_ids": [c.chunk_id for c in chunks]}
            (index_dir / "chunks.json").write_text(json.dumps(manifest, indent=2))
        return cls(matrix)

    def score_all(self, query_vector: Vector) -> Vector:
        return (self._matrix @ query_vector).astype(np.float32)

    def search(self, query_vector: Vector, top_k: int) -> list[tuple[int, float]]:
        scores = self.score_all(query_vector)
        order = np.argsort(-scores)[:top_k]
        return [(int(i), float(scores[i])) for i in order]
