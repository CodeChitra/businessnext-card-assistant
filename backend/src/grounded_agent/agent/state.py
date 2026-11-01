from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict

from grounded_agent.domain.response import (
    AgentResponse,
    DraftResponse,
    IntentResult,
    ServiceRequestRef,
)
from grounded_agent.guardrails.input_guard import InputFlags
from grounded_agent.llm.structured import LLMCall
from grounded_agent.policy.rules import PolicyAssessment
from grounded_agent.retrieval.base import RetrievalResult

Simulate = Literal["timeout", "primary_down"]


class Turn(TypedDict):
    role: Literal["customer", "assistant"]
    content: str


class AgentState(TypedDict, total=False):
    # Inputs (per turn)
    customer_id: str
    message: str
    simulate: Simulate | None
    started_at: float

    # Carried across turns by the checkpointer
    history: Annotated[list[Turn], operator.add]

    # Per-turn working state (reset by input_guard each turn)
    greeting_kind: str | None  # set when the whole message is a greeting, thanks or goodbye
    scope_block: str | None  # 'injection': refused up front, no model call, no human review
    flags: InputFlags
    account: dict[str, Any] | None
    degraded: bool
    degraded_reason: str | None
    intent: IntentResult
    retrieval: RetrievalResult
    assessment: PolicyAssessment
    draft: DraftResponse | None
    validation_errors: list[str]
    repairs: int
    llm_calls: list[LLMCall]
    safe_fallback: bool
    service_request: ServiceRequestRef | None
    response: AgentResponse | None  # set early by a short-circuit, or by finalize
