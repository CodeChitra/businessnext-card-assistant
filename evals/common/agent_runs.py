"""Run the real agent over goldens and capture what the judges need.

One run = one customer turn through the full LangGraph agent. For each run we keep the
customer-facing `AgentResponse` plus a `Grounding`: the chunks the retriever returned and the
exact context the generator was shown (policy chunks, account facts, rule outcomes). The
RAG-triad metrics judge against that context, so a claim about the customer's own account is
checked against the account facts the model actually received, not against policy text alone.

Two modes:
  - live retrieval   (pipeline and application evals)
  - pinned retrieval (generation eval): `PinnedRetriever` returns the golden's gold chunks, so
    the generator is the only moving part. Everything else (tools, rules, classifier, citation
    validator) still runs for real.

Runs are cached on disk so a judge hiccup does not cost a second round of agent calls.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import re
import time
import uuid
from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from pydantic import BaseModel

from grounded_agent.agent.context import build_generation_context
from grounded_agent.agent.deps import AgentDeps
from grounded_agent.agent.graph import build_graph
from grounded_agent.agent.nodes.respond import DEGRADED_PREFIX
from grounded_agent.agent.service import AgentService
from grounded_agent.bootstrap import CHECKPOINT_TYPES, Runtime, build_runtime
from grounded_agent.config.settings import REPO_ROOT, Settings, get_settings
from grounded_agent.domain.response import AgentResponse
from grounded_agent.llm.structured import StructuredLLM
from grounded_agent.retrieval.base import Embedder, RetrievalResult, RetrievedChunk

# "Today" for the rules that depend on it (6-month gap, re-KYC overdue); pinned for repeatability.
EVAL_AS_OF = date(2026, 8, 25)
CACHE_DIR = REPO_ROOT / "evals" / ".cache"
RUN_TIMEOUT_S = 300.0

_REQUEST_NOTE = re.compile(r"\n*I've raised request SR-[A-Z0-9]+[^\n]*$")


class RetrievedView(BaseModel):
    chunk_id: str
    trust: str
    title: str
    text: str
    via: str


class Grounding(BaseModel):
    """What the pipeline retrieved and what the generator was shown."""

    retrieved: list[RetrievedView]
    policy_context: list[str]  # trusted chunks shown to the generator (retrieved + rule-pinned)
    account_facts: str
    rule_outcomes: str
    precedence_notes: str
    miss: bool
    intent: str | None

    def retrieval_context(self) -> list[str]:
        """What the retriever returned, for contextual relevancy."""
        return [
            f"[{c.chunk_id} | trust={c.trust}] {c.title}\n{c.text}" for c in self.retrieved
        ] or ["(nothing retrieved)"]

    def faithfulness_context(self) -> list[str]:
        """Everything the generator could legitimately rely on, for faithfulness."""
        context = list(self.policy_context)
        context.append(f"ACCOUNT FACTS:\n{self.account_facts}")
        context.append(f"RULE OUTCOMES:\n{self.rule_outcomes}")
        if self.precedence_notes.strip() not in ("", "(none)"):
            context.append(f"PRECEDENCE NOTES:\n{self.precedence_notes}")
        return context


class AgentRun(BaseModel):
    id: str
    customer_id: str
    question: str
    simulate: str | None = None
    response: AgentResponse | None = None
    grounding: Grounding | None = None
    error: str | None = None
    wall_ms: int = 0

    @property
    def ok(self) -> bool:
        return self.response is not None and self.grounding is not None


def generator_text(response: AgentResponse) -> str:
    """The model's own words: strips what the system appends (request receipt, degraded notice)."""
    text = response.message
    if response.degraded and text.startswith(DEGRADED_PREFIX):
        text = text[len(DEGRADED_PREFIX) :].lstrip()
    return _REQUEST_NOTE.sub("", text).rstrip()


class PinnedRetriever:
    """Returns fixed chunks whatever the query: retrieval held constant for generator evals."""

    def __init__(self, chunk_ids: Sequence[str], lookup: Callable[[str], Any]) -> None:
        chunks = []
        for cid in chunk_ids:
            chunk = lookup(cid)
            if chunk is None:
                raise KeyError(f"gold chunk {cid!r} is not in the corpus")
            chunks.append(chunk)
        self._chunks = chunks

    def retrieve(self, query: str | Sequence[str], top_k: int | None = None) -> RetrievalResult:
        label = query if isinstance(query, str) else " | ".join(query)
        hits = tuple(
            RetrievedChunk(
                chunk=c,
                rrf_score=1.0,
                bm25_score=0.0,
                dense_score=0.0,
                bm25_rank=None,
                dense_rank=None,
                via="search",
            )
            for c in self._chunks
        )
        return RetrievalResult(query=label, hits=hits, miss=not hits)


def eval_settings(base: Settings | None = None) -> Settings:
    """Pinned clock, and no random tool timeouts: a case times out only when it says so."""
    return (base or get_settings()).model_copy(
        update={"as_of_date": EVAL_AS_OF, "tool_timeout_rate": 0.0, "tool_fault_seed": 0}
    )


class EvalHarness:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        llm: StructuredLLM | None = None,
        embedder: Embedder | None = None,
    ) -> None:
        self.settings = eval_settings(settings)
        self.runtime: Runtime = build_runtime(
            self.settings, llm=llm, embedder=embedder, load_env=False
        )
        self.deps: AgentDeps = self.runtime.deps

    def service(self, pinned_chunks: Sequence[str] | None = None) -> AgentService:
        if pinned_chunks is None:
            return self.runtime.agent
        deps = dataclasses.replace(
            self.deps, retriever=PinnedRetriever(pinned_chunks, self.deps.chunk_index.get_chunk)
        )
        return AgentService(
            build_graph(
                deps,
                checkpointer=InMemorySaver(
                    serde=JsonPlusSerializer(allowed_msgpack_modules=CHECKPOINT_TYPES)
                ),
            ),
            today=deps.today,
            prompt_versions=deps.prompts.versions(),
            max_concurrent_turns=self.settings.max_concurrent_turns,
        )

    def _grounding(self, state: dict[str, Any]) -> Grounding:
        ctx = build_generation_context(state, self.deps)  # type: ignore[arg-type]
        retrieval = state.get("retrieval")
        intent = state.get("intent")
        return Grounding(
            retrieved=[
                RetrievedView(
                    chunk_id=h.chunk.chunk_id,
                    trust=h.chunk.trust.value,
                    title=h.chunk.title,
                    text=h.chunk.text,
                    via=h.via,
                )
                for h in (retrieval.hits if retrieval else ())
            ],
            policy_context=[
                f"[{cid}] {text}" for cid, text in ctx.validation.policy_chunks.items()
            ],
            account_facts=ctx.prompt_values["account_facts"],
            rule_outcomes=ctx.prompt_values["rule_outcomes"],
            precedence_notes=ctx.prompt_values["precedence_notes"],
            miss=bool(retrieval and retrieval.miss),
            intent=intent.intent if intent else None,
        )

    async def run_one(
        self,
        golden_id: str,
        customer_id: str,
        question: str,
        *,
        simulate: str | None = None,
        pinned_chunks: Sequence[str] | None = None,
        timeout_s: float = RUN_TIMEOUT_S,
    ) -> AgentRun:
        run = AgentRun(id=golden_id, customer_id=customer_id, question=question, simulate=simulate)
        started = time.perf_counter()
        try:
            service = self.service(pinned_chunks)
            thread = f"eval-{golden_id}-{uuid.uuid4().hex[:8]}"
            run.response = await asyncio.wait_for(
                service.run(customer_id, question, thread_id=thread, simulate=simulate),  # type: ignore[arg-type]
                timeout_s,
            )
            run.grounding = self._grounding(await service.snapshot(thread))
        except Exception as exc:  # recorded per case, never fatal to the batch
            run.error = f"{type(exc).__name__}: {str(exc)[:240]}"
        run.wall_ms = int((time.perf_counter() - started) * 1000)
        return run


@dataclasses.dataclass(frozen=True)
class RunRequest:
    id: str
    customer_id: str
    question: str
    simulate: str | None = None
    pinned_chunks: tuple[str, ...] | None = None


async def _run_all(
    harness: EvalHarness,
    requests: Sequence[RunRequest],
    max_concurrent: int,
    on_done: Callable[[AgentRun, int, int], None] | None,
) -> list[AgentRun]:
    semaphore = asyncio.Semaphore(max_concurrent)
    done = 0

    async def guarded(req: RunRequest) -> AgentRun:
        nonlocal done
        async with semaphore:
            run = await harness.run_one(
                req.id,
                req.customer_id,
                req.question,
                simulate=req.simulate,
                pinned_chunks=req.pinned_chunks,
            )
        done += 1
        if on_done:
            on_done(run, done, len(requests))
        return run

    return list(await asyncio.gather(*(guarded(r) for r in requests)))


def run_all(
    harness: EvalHarness,
    requests: Sequence[RunRequest],
    *,
    max_concurrent: int = 3,
    on_done: Callable[[AgentRun, int, int], None] | None = None,
) -> list[AgentRun]:
    return asyncio.run(_run_all(harness, requests, max_concurrent, on_done))


def announce(run: AgentRun, done: int, total: int) -> None:
    outcome = run.error or (run.response.behaviour if run.response else "?")
    print(f"  [{done}/{total}] {run.id}: {outcome} ({run.wall_ms / 1000:.1f}s)", flush=True)


# --- on-disk cache ------------------------------------------------------------------------


def cache_path(suite: str) -> Path:
    return CACHE_DIR / f"{suite}.runs.json"


def save_runs(suite: str, runs: Sequence[AgentRun]) -> Path:
    path = cache_path(suite)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[" + ",\n".join(r.model_dump_json() for r in runs) + "]\n")
    return path


def load_runs(suite: str) -> dict[str, AgentRun]:
    path = cache_path(suite)
    if not path.exists():
        raise FileNotFoundError(f"no cached runs at {path}; run once without --reuse-runs")
    return {r.id: r for r in (AgentRun.model_validate(o) for o in _json_list(path))}


def _json_list(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text())
    assert isinstance(data, list)
    return data
