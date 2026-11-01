"""generate, validate and repair nodes."""

from __future__ import annotations

import contextlib
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from grounded_agent.agent.context import build_generation_context
from grounded_agent.agent.deps import AgentDeps
from grounded_agent.agent.state import AgentState
from grounded_agent.domain.response import DraftResponse
from grounded_agent.guardrails.citation_validator import validate_citations
from grounded_agent.guardrails.output_guard import check_actions, check_output
from grounded_agent.llm.structured import LLMUnavailable, force_primary_down

MAX_REPAIRS = 1


def _primary_fault(state: AgentState) -> Any:
    return (
        force_primary_down()
        if state.get("simulate") == "primary_down"
        else contextlib.nullcontext()
    )


class GenerateNode:
    def __init__(self, deps: AgentDeps) -> None:
        self._deps = deps

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        prompt = self._deps.prompts.get("generate")
        ctx = build_generation_context(state, self._deps)
        messages = [
            SystemMessage(prompt.system),
            HumanMessage(prompt.render_user(**ctx.prompt_values)),
        ]
        try:
            with _primary_fault(state):
                result = await self._deps.llm.generate("generate", messages, DraftResponse)
        except LLMUnavailable:
            return {"draft": None, "safe_fallback": True}
        return {"draft": result.value, "llm_calls": [*state.get("llm_calls", []), result.call]}


class RepairNode:
    """One corrective pass with the validator's errors fed back to the model."""

    def __init__(self, deps: AgentDeps) -> None:
        self._deps = deps

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        gen, repair = self._deps.prompts.get("generate"), self._deps.prompts.get("repair")
        ctx = build_generation_context(state, self._deps)
        draft = state["draft"]
        assert draft is not None
        messages = [
            SystemMessage(f"{gen.system}\n\n{repair.system}"),
            HumanMessage(gen.render_user(**ctx.prompt_values)),
            HumanMessage(
                repair.render_user(
                    draft=draft.model_dump_json(indent=2),
                    errors="\n".join(f"- {e}" for e in state["validation_errors"]),
                )
            ),
        ]
        repairs = state.get("repairs", 0) + 1
        try:
            with _primary_fault(state):
                result = await self._deps.llm.generate("repair", messages, DraftResponse)
        except LLMUnavailable:
            return {"draft": None, "safe_fallback": True, "repairs": repairs}
        return {
            "draft": result.value,
            "repairs": repairs,
            "llm_calls": [*state.get("llm_calls", []), result.call],
        }


class ValidateNode:
    def __init__(self, deps: AgentDeps) -> None:
        self._deps = deps

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        draft: DraftResponse | None = state.get("draft")
        if draft is None:
            return {"validation_errors": ["no draft produced"]}
        ctx = build_generation_context(state, self._deps)
        errors = validate_citations(draft, ctx.validation)
        # The guard needs the full record (incl. internal fields) to detect a score leak.
        errors += check_output(
            draft, state["assessment"], state["intent"].intent, state.get("account")
        )
        errors += check_actions(draft, state["assessment"], state["intent"], state.get("flags"))
        return {"validation_errors": errors}


def route_after_validate(state: AgentState) -> str:
    if state.get("safe_fallback") or state.get("draft") is None:
        return "safe_fallback"
    if not state.get("validation_errors"):
        return "act"
    if state.get("repairs", 0) < MAX_REPAIRS:
        return "repair"
    return "safe_fallback"
