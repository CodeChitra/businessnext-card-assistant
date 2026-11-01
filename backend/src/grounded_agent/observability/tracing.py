"""LangSmith tracing.

Tracing is opt-in by environment (`LANGSMITH_TRACING=true` + `LANGSMITH_API_KEY`). With the
flag on but no key, tracing is switched off with a warning instead of erroring per request,
so the app runs identically on a machine without LangSmith.

LangChain / LangGraph runs are traced automatically; our own components are wrapped with
`traceable` so they appear as typed spans (a retriever span renders its documents).
"""

from __future__ import annotations

import logging
import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from langsmith import get_current_run_tree, traceable

from grounded_agent.retrieval.base import RetrievalResult, Retriever

log = logging.getLogger(__name__)

DEFAULT_PROJECT = "grounded-card-agent"
_TRUTHY = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class TracingStatus:
    enabled: bool
    project: str | None
    reason: str


def configure_tracing(default_project: str = DEFAULT_PROJECT) -> TracingStatus:
    wanted = os.environ.get("LANGSMITH_TRACING", "").lower() in _TRUTHY
    has_key = bool(os.environ.get("LANGSMITH_API_KEY"))
    if not wanted:
        return TracingStatus(False, None, "LANGSMITH_TRACING is not enabled")
    if not has_key:
        os.environ["LANGSMITH_TRACING"] = "false"
        log.warning("LANGSMITH_TRACING is on but LANGSMITH_API_KEY is missing; tracing disabled")
        return TracingStatus(False, None, "LANGSMITH_API_KEY missing")
    project = os.environ.setdefault("LANGSMITH_PROJECT", default_project)
    return TracingStatus(True, project, "enabled")


def _as_documents(result: RetrievalResult) -> list[dict[str, Any]]:
    """LangSmith's retriever format: renders each chunk with its scores in the trace UI."""
    return [
        {
            "type": "Document",
            "page_content": h.chunk.text,
            "metadata": {
                "chunk_id": h.chunk.chunk_id,
                "doc_id": h.chunk.doc_id,
                "title": h.chunk.title,
                "version": h.chunk.version,
                "trust": h.chunk.trust.value,
                "via": h.via,
                "rrf_score": h.rrf_score,
                "bm25_score": h.bm25_score,
                "dense_score": h.dense_score,
                "bm25_rank": h.bm25_rank,
                "dense_rank": h.dense_rank,
            },
        }
        for h in result.hits
    ]


class TracedRetriever:
    """Decorator that records each retrieval as a LangSmith `retriever` span."""

    def __init__(self, inner: Retriever, name: str = "hybrid_retriever") -> None:
        self._inner = inner
        self._name = name

    def __getattr__(self, item: str) -> Any:
        return getattr(self._inner, item)

    def retrieve(self, query: str | Sequence[str], top_k: int | None = None) -> RetrievalResult:
        captured: list[RetrievalResult] = []

        @traceable(run_type="retriever", name=self._name, tags=["retrieval"])
        def _run(queries: list[str], top_k: int | None) -> list[dict[str, Any]]:
            result = self._inner.retrieve(queries, top_k)
            captured.append(result)
            run = get_current_run_tree()
            if run is not None:
                run.metadata.update(
                    {
                        "retrieval_miss": result.miss,
                        "num_queries": len(queries),
                        "num_hits": len(result.hits),
                        "xref_hits": sum(h.via == "xref" for h in result.hits),
                        "non_policy_hits": sum(
                            h.chunk.trust.value == "non_policy" for h in result.hits
                        ),
                    }
                )
                if result.miss:
                    run.tags = [*(run.tags or []), "retrieval_miss"]
            return _as_documents(result)

        queries = [query] if isinstance(query, str) else list(query)
        _run(queries, top_k)
        return captured[0]
