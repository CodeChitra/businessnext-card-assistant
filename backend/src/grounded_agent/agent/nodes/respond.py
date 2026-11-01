"""Short-circuit responses, safe fallback, tool action and the final response assembly."""

from __future__ import annotations

import re
import time
from typing import Any

from langsmith import get_current_run_tree

from grounded_agent.agent.deps import AgentDeps
from grounded_agent.agent.state import AgentState
from grounded_agent.domain.errors import InvalidCategory, ToolError
from grounded_agent.domain.response import (
    AgentResponse,
    Citation,
    Claim,
    DraftResponse,
    DraftServiceRequest,
    ResponseMeta,
    ServiceRequestRef,
)
from grounded_agent.guardrails.follow_ups import clean_follow_ups, starter_follow_ups
from grounded_agent.observability.metrics import summarise_calls
from grounded_agent.policy.routing import FALLBACK_QUEUE

OTHER_CUSTOMER = (
    "I can only help with your own account, so I can't share or act on details about "
    "another customer."
)
NOT_FOUND = (
    "I couldn't find an account linked to your profile, so I can't answer questions about "
    "it. Please check your details or contact us through your usual channel."
)
OUT_OF_SCOPE = (
    "I can only help with questions about your card, credit and payments, so I can't help "
    "with that one. I'm glad to help with things like your credit limit, fees, a payment you "
    "don't recognise or how our card policies work."
)
GREETINGS = {
    "hello": (
        "Hello! I'm your card assistant. I can help with your credit limit, fees and charges, "
        "payments, disputes and how our card policies work. What would you like to know?"
    ),
    "thanks": "You're welcome! Is there anything else about your card I can help with?",
    "bye": (
        "Thank you for getting in touch. If you have more questions about your card, "
        "I'm here to help."
    ),
    "about": (
        "I'm your card assistant. I can explain your credit limit and the rules for an "
        "increase, fees and charges, payments, disputes and statements, using our card "
        "policies and your account details. What would you like to know?"
    ),
}
INJECTION_REFUSAL = (
    "I can only act on our card policies, so I can't follow that instruction. I'm glad to "
    "help with questions about your card, limit, fees or payments."
)
UNCOVERED = "I couldn't find an answer to this in our policies, and I don't want to guess."
SAFE_FALLBACK = (
    "I'm sorry, I can't give you a reliable answer to this right now. I've passed your "
    "question to our team so that a colleague can follow up with you."
)
DEGRADED_PREFIX = (
    "I can't access your account details right now, so I can only share general policy information."
)


def route_after_guard(state: AgentState) -> str:
    if state["flags"].other_customer_ids or state.get("greeting_kind"):
        return "short_circuit"
    return "classify"


# Social or off-topic messages are answered here, before any account lookup, retrieval, rules
# or generation: nothing the customer asked needs those steps.
SCOPE_INTENTS = frozenset({"out_of_scope", "greeting"})


def route_after_classify(state: AgentState) -> str:
    if state.get("scope_block") or state["intent"].intent in SCOPE_INTENTS:
        return "short_circuit"
    return "load_account"


def route_after_account(state: AgentState) -> str:
    return "short_circuit" if state.get("degraded_reason") == "customer_not_found" else "retrieve"


def route_after_retrieve(state: AgentState) -> str:
    # A banking question the policies do not cover: say so and hand it to a person, without
    # spending a generation on it. In-domain intents continue even on a retrieval miss: rules
    # pin their own chunks, and the citation validator still blocks any unsupported claim.
    uncovered = state["retrieval"].miss and state["intent"].intent == "other"
    return "uncovered" if uncovered else "policy"


class ShortCircuitNode:
    """Fixed replies that never need an LLM: another customer's data, an unknown customer,
    a greeting, or a question outside what this assistant is for (no human review for those)."""

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        kind = state.get("greeting_kind")
        intent = state.get("intent")
        if state.get("flags") and state["flags"].other_customer_ids:
            draft = DraftResponse(behaviour="refuse", message=OTHER_CUSTOMER)
        elif state.get("scope_block") == "injection":
            draft = DraftResponse(behaviour="refuse", message=INJECTION_REFUSAL)
        elif kind:
            draft = DraftResponse(behaviour="answer", message=GREETINGS[kind])
        elif state.get("degraded_reason") == "customer_not_found":
            draft = DraftResponse(behaviour="refuse", message=NOT_FOUND)
        elif intent is not None and intent.intent == "greeting":
            draft = DraftResponse(behaviour="answer", message=GREETINGS["hello"])
        else:
            draft = DraftResponse(behaviour="refuse", message=OUT_OF_SCOPE)
        return {"draft": draft}


_LONG_DIGITS = re.compile(r"\d{6,}")


class UncoveredNode:
    """A banking question the corpus cannot answer: refuse and route to a person.

    The summary carries the question for the reviewer with long digit runs masked, so a card
    number pasted into the chat does not travel into a ticket.
    """

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        question = _LONG_DIGITS.sub("[number]", " ".join(state["message"].split()))[:160]
        draft = DraftResponse(
            behaviour="refuse",
            message=UNCOVERED,
            service_request=DraftServiceRequest(
                category=FALLBACK_QUEUE,
                summary=f"Banking question not covered by the policies; needs a person: {question}",
            ),
        )
        return {"draft": draft}


class SafeFallbackNode:
    """Every LLM failed, or the draft could not be repaired: never show an unchecked answer."""

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        flags = state.get("flags")
        if flags is not None and flags.injection_suspected:
            # The model was unreachable (often a content filter on the attack itself): refuse
            # firmly; an attack does not need a person to follow up.
            return {
                "draft": DraftResponse(behaviour="refuse", message=INJECTION_REFUSAL),
                "safe_fallback": True,  # keeps ActNode from adding any ticket
                "scope_block": "injection",  # and tells the UI: a refusal, not a handover
            }
        draft = DraftResponse(
            behaviour="refuse",
            message=SAFE_FALLBACK,
            service_request=DraftServiceRequest(
                category=FALLBACK_QUEUE,
                summary="Automated assistant could not produce a verified answer; please review.",
            ),
        )
        return {"draft": draft, "safe_fallback": True}


class ActNode:
    """Executes the service request, with the rules engine overriding the model where needed.

    Forbidden tickets (CREDIT_OPS on a mandatory decline, any ticket for a disclosure question)
    are rejected in validation, so the message and the actions cannot disagree. Here:
    - Explicit limit request with no mandatory decline: a CREDIT_OPS request is raised even if
      the model forgot (routing, not approval).
    - Reported dispute: always routed to DISPUTES (POL-SVC-006), never left to model wording.
    - Unrecognised category: GENERAL, as POL-SVC-006 prescribes.
    """

    def __init__(self, deps: AgentDeps) -> None:
        self._deps = deps

    def _requested(self, state: AgentState, draft: DraftResponse) -> DraftServiceRequest | None:
        sr = draft.service_request
        assessment = state.get("assessment")
        intent = state.get("intent")
        if assessment is None or intent is None or state.get("safe_fallback"):
            return sr
        # Forbidden tickets are rejected earlier, in validation (check_actions), so the message
        # never refers to a ticket that is not raised. Here we only add required ones.
        if intent.intent == "dispute" and intent.explicit_request:
            if sr is None or sr.category != "DISPUTES":
                return DraftServiceRequest(
                    category="DISPUTES",
                    summary="Customer reports an unrecognised card transaction.",
                )
            return sr
        if (
            intent.intent == "limit_increase"
            and intent.explicit_request
            and assessment.decision == "refer"
            and sr is None
        ):
            return DraftServiceRequest(
                category="CREDIT_OPS",
                summary="Customer requested a credit limit increase; rules outcome "
                f"{', '.join(assessment.rules_fired) or 'none'}; needs credit officer review.",
            )
        return sr

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        draft = state.get("draft")
        if draft is None:
            return {}
        wanted = self._requested(state, draft)
        if wanted is None:
            return {"draft": draft.model_copy(update={"service_request": None})}

        tool = self._deps.service_tool
        try:
            sr = await tool.raise_service_request(
                state["customer_id"], wanted.category, wanted.summary
            )
        except InvalidCategory:
            sr = await tool.raise_service_request(
                state["customer_id"],
                FALLBACK_QUEUE,
                f"[uncategorised: {wanted.category}] {wanted.summary}",
            )
        except (ToolError, ValueError):
            note = " I wasn't able to raise a request automatically just now; please try again."
            return {"draft": draft.model_copy(update={"message": draft.message + note})}

        spec = self._deps.queues[sr["queue"]]
        note = (
            f"\n\nI've raised request {sr['request_id']} ({spec.intent.lower()}). "
            f"You can expect an update within {spec.sla_text}."
        )
        behaviour = draft.behaviour
        if behaviour == "answer" and wanted is not draft.service_request:
            behaviour = "raise_request"
        return {
            "draft": draft.model_copy(
                update={"message": draft.message + note, "behaviour": behaviour}
            ),
            "service_request": ServiceRequestRef(**sr),
        }


class FinalizeNode:
    def __init__(self, deps: AgentDeps) -> None:
        self._deps = deps

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        draft = state["draft"]
        assert draft is not None
        assessment = state.get("assessment")
        degraded = bool(state.get("degraded"))
        message = draft.message
        if degraded and not state.get("safe_fallback") and DEGRADED_PREFIX not in message:
            message = f"{DEGRADED_PREFIX} {message}"

        usage = summarise_calls(state.get("llm_calls", []), self._deps.prices)
        generate_calls = [
            c for c in state.get("llm_calls", []) if c.purpose in ("generate", "repair")
        ]
        run = get_current_run_tree()
        meta = ResponseMeta(
            model=generate_calls[-1].model if generate_calls else None,
            prompt_versions=self._deps.prompts.versions(),
            input_tokens=int(usage["input_tokens"]),  # type: ignore[call-overload]
            output_tokens=int(usage["output_tokens"]),  # type: ignore[call-overload]
            cost_usd=float(usage["cost_usd"]),  # type: ignore[arg-type]
            latency_ms=int(
                (time.perf_counter() - state.get("started_at", time.perf_counter())) * 1000
            ),
            trace_id=str(run.trace_id) if run is not None else None,
            fallback_used=bool(usage["fallback_used"]),
            repaired=state.get("repairs", 0) > 0,
            # "Handed over to a person". An injection refusal is a plain refusal, not a handover.
            safe_fallback=bool(state.get("safe_fallback"))
            and state.get("scope_block") != "injection",
            retrieval_miss=bool(state.get("retrieval") and state["retrieval"].miss),
            rules_fired=assessment.rules_fired if assessment else [],
        )
        # Reason codes come from the rules whenever the rules decline, including when the
        # turn is a refusal of an injected instruction on top of a mandatory decline.
        reason_codes = (
            assessment.reason_codes
            if assessment
            and assessment.decision == "decline"
            and draft.behaviour in ("decline_with_reason", "refuse")
            else []
        )
        follow_ups = clean_follow_ups(
            draft.follow_ups,
            suppress_sales=assessment.suppress_sales if assessment else True,
            asked=state["message"],
        )
        # Suggestions should always be there to tap. When the model offered none (a greeting, a
        # refusal), fall back to safe starters, except where they would be wrong: a handover
        # to a person, an outage of the account service, or an unknown customer.
        no_starters = (
            state.get("safe_fallback")
            or degraded
            or state.get("degraded_reason") == "customer_not_found"
        )
        if state.get("safe_fallback"):
            follow_ups = []  # a handover is not a conversation
        elif not follow_ups and not no_starters:
            follow_ups = starter_follow_ups()
        response = AgentResponse(
            behaviour=draft.behaviour,
            message=message,
            claims=[
                Claim(text=c.text, citations=[Citation.parse(r) for r in c.citations])
                for c in draft.claims
            ],
            reason_codes=reason_codes,
            service_request=state.get("service_request"),
            degraded=degraded,
            follow_ups=follow_ups,
            meta=meta,
        )
        return {
            "response": response,
            "history": [
                {"role": "customer", "content": state["message"]},
                {"role": "assistant", "content": message},
            ],
        }
