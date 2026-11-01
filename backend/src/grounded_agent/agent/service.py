"""Public entry point: one customer turn in, progress events and one AgentResponse out.

`stream()` yields a progress event per graph node and then exactly one final event carrying
the validated AgentResponse. Raw model tokens are deliberately never streamed: text reaches
the customer only after citation validation and the output guards (SPEC 10.1).

Owns the LangSmith root span for the turn. Graph nodes appear as child spans (LangGraph
traces them), the retriever as a `retriever` span, LLM calls as `llm` spans with tokens.
The root span carries the outcome as metadata so traces can be filtered by behaviour,
degraded mode, retrieval misses, rules fired, model and prompt versions.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from langsmith import get_current_run_tree, traceable

from grounded_agent.agent.state import Simulate
from grounded_agent.domain.response import AgentResponse

log = logging.getLogger(__name__)

# Customer-facing progress labels. Internal node names never reach the UI.
PROGRESS_LABELS: dict[str, str] = {
    "input_guard": "Reading your message",
    "load_account": "Checking your account",
    "classify": "Understanding your question",
    "retrieve": "Searching our policies",
    "policy": "Applying policy rules",
    "generate": "Drafting a grounded answer",
    "validate": "Checking every claim against its source",
    "repair": "Correcting an unsupported claim",
    "safe_fallback": "Preparing a safe response",
    "short_circuit": "Preparing a response",
    "uncovered": "Passing your question to our team",
    "act": "Checking for follow-up actions",
    "finalize": "Finalising",
}


@dataclass(frozen=True)
class AgentEvent:
    type: Literal["progress", "final"]
    data: dict[str, Any] = field(default_factory=dict)


def _progress_detail(node: str, update: dict[str, Any]) -> dict[str, Any]:
    """Small, customer-safe facts about a step (no internal ids or scores)."""
    if node == "load_account":
        return {"degraded": bool(update.get("degraded"))}
    if node == "retrieve" and update.get("retrieval") is not None:
        r = update["retrieval"]
        return {"sources_found": len({h.chunk.doc_id for h in r.hits}), "miss": r.miss}
    if node == "validate":
        return {"issues_found": len(update.get("validation_errors") or [])}
    return {}


class AgentService:
    def __init__(
        self,
        graph: Any,
        *,
        today: date,
        prompt_versions: dict[str, str],
        max_concurrent_turns: int = 16,
    ) -> None:
        self._graph = graph
        self._today = today
        self._prompt_versions = prompt_versions
        # Bounds concurrent turns (and so concurrent LLM calls) per process.
        self._semaphore = asyncio.Semaphore(max_concurrent_turns)

    async def run(
        self,
        customer_id: str,
        message: str,
        thread_id: str | None = None,
        simulate: Simulate | None = None,
        rewind_to: int | None = None,
    ) -> AgentResponse:
        final: AgentResponse | None = None
        async for event in self.stream(customer_id, message, thread_id, simulate, rewind_to):
            if event.type == "final":
                final = AgentResponse.model_validate(event.data)
        assert final is not None, "graph finished without a final response"
        return final

    async def _thread_for(
        self, customer_id: str, thread_id: str | None, rewind_to: int | None
    ) -> str:
        """The thread this turn runs on.

        - No thread: a new one.
        - A thread that belongs to another customer is never continued (its history would reach
          the model's context): a new one is used instead.
        - `rewind_to` (edit a message, replay an answer): fork the thread, keeping only its first
          N completed turns. The history is the server's own, never client-supplied, so a user
          cannot forge assistant turns.
        """
        if thread_id is None:
            return str(uuid.uuid4())
        state = await self.snapshot(thread_id)
        if state and state.get("customer_id") != customer_id:
            log.warning("thread %s does not belong to this customer; starting a new one", thread_id)
            return str(uuid.uuid4())
        if rewind_to is None:
            return thread_id
        history = state.get("history") or []
        if not state:
            log.info("rewind of unknown thread %s (server restarted?); history lost", thread_id)
        fork = str(uuid.uuid4())
        await self._graph.aupdate_state(
            {"configurable": {"thread_id": fork}},
            {"history": history[: rewind_to * 2], "customer_id": customer_id},  # 2 per turn
            as_node="finalize",
        )
        return fork

    async def snapshot(self, thread_id: str) -> dict[str, Any]:
        """Final graph state of a thread: what the turn retrieved, decided and saw.

        For evals and debugging; deliberately not exposed over HTTP (it holds the full
        account record).
        """
        snap = await self._graph.aget_state({"configurable": {"thread_id": thread_id}})
        return dict(snap.values)

    @traceable(run_type="chain", name="card_agent_turn")
    async def stream(
        self,
        customer_id: str,
        message: str,
        thread_id: str | None = None,
        simulate: Simulate | None = None,
        rewind_to: int | None = None,
    ) -> AsyncIterator[AgentEvent]:
        thread_id = await self._thread_for(customer_id, thread_id, rewind_to)
        run = get_current_run_tree()
        if run is not None:
            run.metadata.update(
                {
                    "customer_id": customer_id,
                    "thread_id": thread_id,
                    "as_of_date": self._today.isoformat(),
                    "prompt_versions": self._prompt_versions,
                    "simulate": simulate,
                }
            )
        response: AgentResponse | None = None
        async with self._semaphore:
            async for chunk in self._graph.astream(
                {"customer_id": customer_id, "message": message, "simulate": simulate},
                config={"configurable": {"thread_id": thread_id}, "run_name": "card_agent_graph"},
                stream_mode="updates",
            ):
                for node, update in chunk.items():
                    update = update or {}
                    if node in PROGRESS_LABELS and node != "finalize":
                        yield AgentEvent(
                            "progress",
                            {
                                "step": node,
                                "label": PROGRESS_LABELS[node],
                                **_progress_detail(node, update),
                            },
                        )
                    if update.get("response") is not None:
                        response = update["response"]
        if response is None:
            raise RuntimeError("graph finished without a final response")
        response = self._annotate(run, response, thread_id)
        yield AgentEvent("final", response.model_dump(mode="json"))

    @staticmethod
    def _annotate(run: Any, response: AgentResponse, thread_id: str) -> AgentResponse:
        meta_update: dict[str, Any] = {"thread_id": thread_id}
        if run is not None:
            meta_update["trace_id"] = str(run.trace_id)
            run.metadata.update(
                {
                    "behaviour": response.behaviour,
                    "degraded": response.degraded,
                    "retrieval_miss": response.meta.retrieval_miss,
                    "rules_fired": response.meta.rules_fired,
                    "model": response.meta.model,
                    "fallback_used": response.meta.fallback_used,
                    "repaired": response.meta.repaired,
                    "safe_fallback": response.meta.safe_fallback,
                    "service_request_queue": response.service_request.queue
                    if response.service_request
                    else None,
                    "input_tokens": response.meta.input_tokens,
                    "output_tokens": response.meta.output_tokens,
                    "cost_usd": response.meta.cost_usd,
                }
            )
            run.tags = [*(run.tags or []), f"behaviour:{response.behaviour}"]
            if response.degraded:
                run.tags.append("degraded")
            if response.meta.safe_fallback:
                run.tags.append("safe_fallback")
        return response.model_copy(update={"meta": response.meta.model_copy(update=meta_update)})
