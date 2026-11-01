from __future__ import annotations

from collections.abc import Sequence
from typing import Literal, Protocol

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict

from grounded_agent.domain.policy import PolicyChunk

Vector = NDArray[np.float32]


class Embedder(Protocol):
    model_name: str

    def embed_documents(self, texts: list[str]) -> Vector: ...

    def embed_query(self, text: str) -> Vector: ...


class VectorStore(Protocol):
    def search(self, query_vector: Vector, top_k: int) -> list[tuple[int, float]]:
        """Return (chunk_index, cosine_similarity) pairs, best first."""
        ...

    def score_all(self, query_vector: Vector) -> Vector: ...


class RetrievedChunk(BaseModel):
    model_config = ConfigDict(frozen=True)

    chunk: PolicyChunk
    rrf_score: float
    bm25_score: float
    dense_score: float
    bm25_rank: int | None
    dense_rank: int | None
    via: Literal["search", "xref"]


class RetrievalResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    query: str
    hits: tuple[RetrievedChunk, ...]
    miss: bool  # no candidate cleared the relevance floors

    @property
    def chunk_ids(self) -> list[str]:
        return [h.chunk.chunk_id for h in self.hits]


class Retriever(Protocol):
    def retrieve(self, query: str | Sequence[str], top_k: int | None = None) -> RetrievalResult: ...
