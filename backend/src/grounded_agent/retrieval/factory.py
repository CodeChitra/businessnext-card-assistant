from __future__ import annotations

from grounded_agent.config.settings import Settings
from grounded_agent.retrieval.base import Embedder
from grounded_agent.retrieval.bm25 import BM25Index
from grounded_agent.retrieval.chunker import chunk_corpus
from grounded_agent.retrieval.embeddings import FastEmbedEmbedder
from grounded_agent.retrieval.hybrid import HybridRetriever
from grounded_agent.retrieval.loader import load_corpus
from grounded_agent.retrieval.vector_store import NumpyVectorStore


def build_retriever(settings: Settings, embedder: Embedder | None = None) -> HybridRetriever:
    chunks = chunk_corpus(load_corpus(settings.corpus_dir))
    embedder = embedder or FastEmbedEmbedder(
        settings.embedding_model, settings.cache_dir / "models"
    )
    return HybridRetriever(
        chunks,
        BM25Index(chunks),
        NumpyVectorStore.build(chunks, embedder, settings.cache_dir),
        embedder,
        top_k=settings.retrieval_top_k,
        rrf_k=settings.rrf_k,
        dense_min_score=settings.dense_min_score,
        bm25_min_score=settings.bm25_min_score,
    )
