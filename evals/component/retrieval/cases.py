"""Turn retrieval goldens into DeepEval test cases by running the retriever standalone."""

from __future__ import annotations

from collections.abc import Callable

from deepeval.test_case import LLMTestCase
from langsmith import tracing_context

from evals.common.datasets import RetrievalGolden
from grounded_agent.config.settings import Settings
from grounded_agent.observability.tracing import TracedRetriever
from grounded_agent.retrieval.base import RetrievalResult, Retriever
from grounded_agent.retrieval.factory import build_retriever

SUITE = "component.retrieval"

# How the query list is formed for each configuration under test.
QUERY_CONFIGS: dict[str, Callable[[RetrievalGolden], list[str]]] = {
    "raw": lambda g: [g.question],
    "expanded": lambda g: [g.question, g.rewrite],
}


def make_retriever(settings: Settings) -> Retriever:
    return TracedRetriever(build_retriever(settings))


def _context(result: RetrievalResult) -> list[str]:
    return [
        f"[{h.chunk.chunk_id} | trust={h.chunk.trust.value}] {h.chunk.title}\n{h.chunk.text}"
        for h in result.hits
    ]


def build_case(golden: RetrievalGolden, config: str, retriever: Retriever) -> LLMTestCase:
    queries = QUERY_CONFIGS[config](golden)
    with tracing_context(
        metadata={"eval_suite": SUITE, "case_id": golden.id, "query_config": config},
        tags=["eval", SUITE, config],
    ):
        result = retriever.retrieve(queries)
    return LLMTestCase(
        name=f"{golden.id}[{config}]",
        input=golden.question,
        expected_output=golden.expected_output,
        retrieval_context=_context(result),
        tags=[*golden.tags, config],
        metadata={
            "case_id": golden.id,
            "config": config,
            "queries": queries,
            "expected_chunks": golden.expected_chunks,
            "expected_miss": golden.expected_miss,
            "miss": result.miss,
            "search_chunks": [h.chunk.chunk_id for h in result.hits if h.via == "search"],
            "all_chunks": result.chunk_ids,
        },
    )
