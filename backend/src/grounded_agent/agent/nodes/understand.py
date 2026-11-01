"""classify, retrieve and policy nodes."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from grounded_agent.agent.deps import AgentDeps
from grounded_agent.agent.state import AgentState
from grounded_agent.domain.account import Account
from grounded_agent.domain.response import IntentResult
from grounded_agent.llm.structured import LLMUnavailable

CLASSIFY_HISTORY = 4  # entries (two exchanges): enough for "and for the other card?"


class ClassifyNode:
    """Intent + a policy-vocabulary rewrite. If the LLM is down, retrieval still runs on the
    raw question and the turn degrades gracefully later."""

    def __init__(self, deps: AgentDeps) -> None:
        self._deps = deps

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        prompt = self._deps.prompts.get("classify")
        recent = (state.get("history") or [])[-CLASSIFY_HISTORY:]
        history = "\n".join(f"{t['role']}: {t['content'][:300]}" for t in recent) or "(none)"
        messages = [
            SystemMessage(prompt.system),
            HumanMessage(prompt.render_user(message=state["message"], history=history)),
        ]
        try:
            result = await self._deps.llm.generate("classify", messages, IntentResult)
        except LLMUnavailable:
            fallback = IntentResult(
                intent="other", search_query=state["message"], explicit_request=False
            )
            flags = state.get("flags")
            if flags is not None and flags.injection_suspected:
                # A provider's content filter often rejects an injection attempt outright. That
                # is a refusal, not an outage: say no firmly and do not open a ticket for it.
                return {"intent": fallback, "scope_block": "injection"}
            return {"intent": fallback}
        return {"intent": result.value, "llm_calls": [*state.get("llm_calls", []), result.call]}


class RetrieveNode:
    def __init__(self, deps: AgentDeps) -> None:
        self._deps = deps

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        intent = state["intent"]
        queries = [state["message"], intent.search_query]
        return {"retrieval": self._deps.retriever.retrieve(queries)}


class PolicyNode:
    def __init__(self, deps: AgentDeps) -> None:
        self._deps = deps

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        raw = state.get("account")
        account = Account.model_validate(raw) if raw else None
        assessment = self._deps.policy.assess(account, state["intent"].intent, self._deps.today)
        return {"assessment": assessment}
