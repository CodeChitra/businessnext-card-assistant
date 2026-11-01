"""input_guard and load_account nodes."""

from __future__ import annotations

import asyncio
import contextlib
import random
import time
from typing import Any

from grounded_agent.agent.deps import AgentDeps
from grounded_agent.agent.state import AgentState
from grounded_agent.domain.errors import CustomerNotFound, UpstreamTimeout
from grounded_agent.guardrails.input_guard import inspect_input
from grounded_agent.guardrails.scope import greeting_kind
from grounded_agent.policy.rules import PolicyAssessment
from grounded_agent.tools.faults import force_timeout

# Fresh per-turn values, so nothing from the previous turn leaks through the checkpointer.
_TURN_RESET: dict[str, Any] = {
    "account": None,
    "degraded": False,
    "degraded_reason": None,
    "draft": None,
    "validation_errors": [],
    "repairs": 0,
    "llm_calls": [],
    "safe_fallback": False,
    "service_request": None,
    "response": None,
    "assessment": PolicyAssessment(decision="none"),
    "greeting_kind": None,
    "scope_block": None,
}


class InputGuardNode:
    async def __call__(self, state: AgentState) -> dict[str, Any]:
        flags = inspect_input(state["message"], state["customer_id"])
        return {
            **_TURN_RESET,
            "flags": flags,
            "greeting_kind": greeting_kind(state["message"]),
            "started_at": time.perf_counter(),
        }


class LoadAccountNode:
    """Calls get_account_state with a per-attempt timeout and jittered retries.

    UpstreamTimeout after the last attempt is not an error path: it switches the turn into
    degraded mode (general policy answers only, no account claims).
    """

    def __init__(self, deps: AgentDeps) -> None:
        self._deps = deps

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        retry = self._deps.retry
        forced = state.get("simulate") == "timeout"
        last_error = "unknown"
        for attempt in range(retry.attempts):
            try:
                with force_timeout() if forced else contextlib.nullcontext():
                    account = await asyncio.wait_for(
                        self._deps.account_tool.get_account_state(state["customer_id"]),
                        timeout=retry.per_attempt_timeout_s,
                    )
                return {"account": account, "degraded": False}
            except CustomerNotFound:
                return {"account": None, "degraded": False, "degraded_reason": "customer_not_found"}
            except (UpstreamTimeout, TimeoutError) as exc:
                last_error = type(exc).__name__
                if attempt + 1 < retry.attempts:
                    delay = retry.backoff_base_s * (2**attempt) * (0.5 + random.random())
                    await asyncio.sleep(delay)
        return {
            "account": None,
            "degraded": True,
            "degraded_reason": f"account service unavailable after {retry.attempts} attempts "
            f"({last_error})",
        }
