"""Response contracts.

Two layers on purpose:
  - `IntentResult` and `DraftResponse` are what the LLM is asked to produce (structured output).
  - `AgentResponse` is what the customer/API receives, assembled by code after validation,
    guards and tool execution. The LLM never writes request ids, SLAs or meta.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Behaviour = Literal["answer", "decline_with_reason", "refuse", "raise_request"]
ReasonCode = Literal["AA01", "AA02", "AA03", "AA04", "AA05", "AA06"]
Intent = Literal[
    "fee",
    "limit_increase",
    "dispute",
    "product_terms",
    "service_request",
    "disclosure",
    "account_info",
    "out_of_scope",
    "greeting",
    "other",
]

ACCOUNT_PREFIX = "account."
RULE_PREFIX = "rule."


# --- LLM-facing schemas ------------------------------------------------------------------


class IntentResult(BaseModel):
    """Classifier output: routing plus a policy-vocabulary query for retrieval."""

    intent: Intent
    search_query: str = Field(
        description="A short query in banking-policy vocabulary for searching the policy "
        "corpus, e.g. 'unauthorised transaction dispute provisional credit'."
    )
    explicit_request: bool = Field(
        description="True only if the customer explicitly asks us to DO something "
        "(increase my limit, block my card, raise a dispute), not just asks a question."
    )


class DraftClaim(BaseModel):
    text: str = Field(description="One factual statement made in the message.")
    citations: list[str] = Field(
        min_length=1,
        description="Ids supporting the claim: policy chunk ids exactly as shown in the "
        "context (e.g. 'POL-FEE-007#body'), account fields as 'account.<field>', or rule "
        "outcomes as 'rule.<RULE_ID>' for decisions and computed values.",
    )


class DraftServiceRequest(BaseModel):
    category: str = Field(description="Exactly one of the queue names listed in the context.")
    summary: str = Field(description="One sentence for the receiving team. No score values.")


class DraftResponse(BaseModel):
    behaviour: Behaviour
    message: str = Field(
        description="Plain-language reply to the customer, in light Markdown (short "
        "paragraphs, '- ' bullets, **bold** for key figures)."
    )
    claims: list[DraftClaim] = Field(default_factory=list)
    reason_codes: list[ReasonCode] = Field(default_factory=list)
    service_request: DraftServiceRequest | None = None
    follow_ups: list[str] = Field(
        default_factory=list,
        description="Up to 3 short questions the customer may ask next, in the customer's "
        "own voice. No numbers or amounts. Empty when refusing or handing off.",
    )


# --- Customer/API-facing schema ----------------------------------------------------------


class Citation(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Literal["policy", "account", "rule"]
    ref: str

    @classmethod
    def parse(cls, ref: str) -> Citation:
        if ref.startswith(ACCOUNT_PREFIX):
            return cls(type="account", ref=ref)
        if ref.startswith(RULE_PREFIX):
            return cls(type="rule", ref=ref)
        return cls(type="policy", ref=ref)


class Claim(BaseModel):
    text: str
    citations: list[Citation] = Field(min_length=1)


class ServiceRequestRef(BaseModel):
    request_id: str
    queue: str
    sla_hours: int


class ResponseMeta(BaseModel):
    model: str | None = None
    prompt_versions: dict[str, str] = Field(default_factory=dict)
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    trace_id: str | None = None
    thread_id: str | None = None  # pass back to continue the conversation
    fallback_used: bool = False
    repaired: bool = False
    safe_fallback: bool = False
    retrieval_miss: bool = False
    rules_fired: list[str] = Field(default_factory=list)


class AgentResponse(BaseModel):
    behaviour: Behaviour
    message: str
    claims: list[Claim] = Field(default_factory=list)
    reason_codes: list[ReasonCode] = Field(default_factory=list)
    service_request: ServiceRequestRef | None = None
    degraded: bool = False
    # Suggested next questions; sanitised by `guardrails.follow_ups` before they get here.
    follow_ups: list[str] = Field(default_factory=list, max_length=3)
    meta: ResponseMeta = Field(default_factory=ResponseMeta)
