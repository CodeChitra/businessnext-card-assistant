"""Hybrid retrieval: BM25 + dense, fused with Reciprocal Rank Fusion.

- RRF uses ranks only, so BM25 and cosine scores never need calibrating against each other.
- Several queries (the raw question plus intent-guided rewrites) are fused in one pass:
  each contributes a BM25 list and a dense list.
- Miss detection is query-level: a miss means no query had any chunk clearing either
  floor. This catches off-domain questions only; an in-domain but uncovered question
  ("travel insurance") still retrieves neighbours, and is refused at generation time,
  where the citation validator makes an uncitable claim impossible.
- Cross-reference expansion adds the best chunk of any document a hit points to
  (e.g. POL-CRD-001 §3 -> POL-CON-004), deterministically.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Sequence

import numpy as np

from grounded_agent.domain.policy import PolicyChunk
from grounded_agent.retrieval.base import (
    Embedder,
    RetrievalResult,
    RetrievedChunk,
    Vector,
    VectorStore,
)
from grounded_agent.retrieval.bm25 import BM25Index


def _ranks(scores: Vector) -> dict[int, int]:
    """1-based rank for every index with a positive score."""
    order = [int(i) for i in np.argsort(-scores) if scores[i] > 0]
    return {idx: rank for rank, idx in enumerate(order, start=1)}


class HybridRetriever:
    def __init__(
        self,
        chunks: list[PolicyChunk],
        bm25: BM25Index,
        vectors: VectorStore,
        embedder: Embedder,
        *,
        top_k: int = 5,
        rrf_k: int = 60,
        dense_min_score: float = 0.55,
        bm25_min_score: float = 3.0,
        cache_size: int = 256,
    ) -> None:
        self._chunks = chunks
        self._bm25 = bm25
        self._vectors = vectors
        self._embedder = embedder
        self._top_k = top_k
        self._rrf_k = rrf_k
        self._dense_min = dense_min_score
        self._bm25_min = bm25_min_score
        self._cache: OrderedDict[tuple[tuple[str, ...], int], RetrievalResult] = OrderedDict()
        self._cache_size = cache_size

    @property
    def chunks(self) -> list[PolicyChunk]:
        return list(self._chunks)

    def get_chunk(self, chunk_id: str) -> PolicyChunk | None:
        return next((c for c in self._chunks if c.chunk_id == chunk_id), None)

    def retrieve(self, query: str | Sequence[str], top_k: int | None = None) -> RetrievalResult:
        queries = [query] if isinstance(query, str) else list(query)
        queries = [q for q in dict.fromkeys(q.strip() for q in queries) if q]
        if not queries:
            raise ValueError("at least one non-empty query is required")
        k = top_k or self._top_k
        key = (tuple(" ".join(q.lower().split()) for q in queries), k)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        result = self._retrieve(queries, k)
        self._cache[key] = result
        if len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)
        return result

    def _retrieve(self, queries: list[str], k: int) -> RetrievalResult:
        n = len(self._chunks)
        fused = np.zeros(n, dtype=np.float64)
        best_bm25 = np.zeros(n, dtype=np.float32)
        best_dense = np.full(n, -1.0, dtype=np.float32)
        best_bm25_rank: dict[int, int] = {}
        best_dense_rank: dict[int, int] = {}
        any_relevant = False

        for q in queries:
            bm25_scores = self._bm25.score_all(q)
            dense_scores = self._vectors.score_all(self._embedder.embed_query(q))
            if np.max(bm25_scores) >= self._bm25_min or np.max(dense_scores) >= self._dense_min:
                any_relevant = True
            for ranks, best_rank in (
                (_ranks(bm25_scores), best_bm25_rank),
                (_ranks(dense_scores), best_dense_rank),
            ):
                for idx, rank in ranks.items():
                    fused[idx] += 1.0 / (self._rrf_k + rank)
                    best_rank[idx] = min(rank, best_rank.get(idx, rank))
            best_bm25 = np.maximum(best_bm25, bm25_scores)
            best_dense = np.maximum(best_dense, dense_scores)

        if not any_relevant:
            return RetrievalResult(query=queries[0], hits=(), miss=True)

        def hit(idx: int, via: str) -> RetrievedChunk:
            return RetrievedChunk(
                chunk=self._chunks[idx],
                rrf_score=round(float(fused[idx]), 6),
                bm25_score=round(float(best_bm25[idx]), 4),
                dense_score=round(float(best_dense[idx]), 4),
                bm25_rank=best_bm25_rank.get(idx),
                dense_rank=best_dense_rank.get(idx),
                via=via,  # type: ignore[arg-type]
            )

        top = [int(i) for i in np.argsort(-fused)[:k] if fused[i] > 0]
        hits = [hit(i, "search") for i in top]

        seen_docs = {self._chunks[i].doc_id for i in top}
        for i in top:
            for ref in self._chunks[i].references:
                if ref in seen_docs:
                    continue
                candidates = [j for j, c in enumerate(self._chunks) if c.doc_id == ref]
                if candidates:
                    best = max(candidates, key=lambda j: float(fused[j]))
                    hits.append(hit(best, "xref"))
                    seen_docs.add(ref)

        return RetrievalResult(query=queries[0], hits=tuple(hits), miss=False)
