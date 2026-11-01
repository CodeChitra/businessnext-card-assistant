"""What the generator sees, and the matching validation context.

Built in one place so the prompt and the validator can never disagree about which chunks
and fields were available. Internal fields (behavioural_score) are removed here: the model
cannot leak what it never receives.
"""

from __future__ import annotations

from dataclasses import dataclass

from grounded_agent.agent.deps import AgentDeps
from grounded_agent.agent.state import AgentState
from grounded_agent.domain.policy import PolicyChunk, Trust
from grounded_agent.guardrails.citation_validator import INTERNAL_ACCOUNT_FIELDS, ValidationContext
from grounded_agent.policy.precedence import notes_for

HISTORY_TURNS = 6


@dataclass(frozen=True)
class GenerationContext:
    prompt_values: dict[str, str]
    validation: ValidationContext


def _chunk_block(c: PolicyChunk) -> str:
    heading = f" — {c.heading}" if c.heading else ""
    return f"[{c.chunk_id}] {c.title}{heading} (v{c.version})\n{c.text}"


def build_generation_context(state: AgentState, deps: AgentDeps) -> GenerationContext:
    retrieval = state.get("retrieval")
    assessment = state["assessment"]
    chunks: dict[str, PolicyChunk] = {}
    if retrieval is not None:
        for h in retrieval.hits:
            chunks[h.chunk.chunk_id] = h.chunk
    for cid in assessment.pinned_chunks:
        chunk = deps.chunk_index.get_chunk(cid)
        if chunk is not None:
            chunks.setdefault(cid, chunk)

    trusted = {cid: c for cid, c in chunks.items() if c.trust is Trust.POLICY}
    untrusted = {cid: c for cid, c in chunks.items() if c.trust is not Trust.POLICY}

    account = state.get("account")
    visible_account = (
        {k: v for k, v in account.items() if k not in INTERNAL_ACCOUNT_FIELDS} if account else None
    )
    account_facts = (
        "\n".join(f"- account.{k}: {v}" for k, v in visible_account.items())
        if visible_account
        else "UNAVAILABLE: the account system did not respond. Do not state or cite any "
        "account-specific fact."
    )

    rule_lines = [
        f"- rule.{f.rule_id} [{f.outcome}]"
        + (f" reason_code={f.reason_code}" if f.reason_code else "")
        + (f": {f.customer_reason}" if f.customer_reason else "")
        + (f" Facts: {'; '.join(f.facts)}." if f.facts else "")
        + f" (cite: {', '.join(f.citations)})"
        for f in assessment.findings
    ]
    decision = f"DECISION: {assessment.decision}"
    if assessment.decision == "decline":
        decision += f" (reason codes: {', '.join(assessment.reason_codes) or 'none'})"

    precedence = notes_for({c.doc_id for c in chunks.values()})
    history = state.get("history") or []
    flags = state.get("flags")
    intent = state.get("intent")

    values = {
        "message": state["message"],
        "history": "\n".join(f"{t['role']}: {t['content']}" for t in history[-HISTORY_TURNS:])
        or "(none)",
        "intent": intent.intent if intent else "other",
        "explicit_request": str(intent.explicit_request if intent else False).lower(),
        "account_facts": account_facts,
        "rule_outcomes": "\n".join([decision, *rule_lines]),
        "sales_suppressed": "yes" if assessment.suppress_sales else "no",
        "policy_context": "\n\n".join(_chunk_block(c) for c in trusted.values()) or "(none)",
        "precedence_notes": "\n".join(f"- {p.note}" for p in precedence) or "(none)",
        "untrusted_notes": "\n\n".join(_chunk_block(c) for c in untrusted.values()) or "(none)",
        "queues": "\n".join(
            f"- {q.queue}: {q.intent} (SLA {q.sla_text})" for q in deps.queues.values()
        ),
        "flags": flags.describe() if flags else "none",
    }
    validation = ValidationContext(
        policy_chunks={cid: c.text for cid, c in trusted.items()},
        untrusted_chunk_ids=frozenset(untrusted),
        account=visible_account,
        rule_texts={
            f"rule.{f.rule_id}": " ".join([f.customer_reason, *f.facts])
            for f in assessment.findings
        },
        extra_grounded_text=(
            *assessment.facts,
            *(f.customer_reason for f in assessment.findings),
        ),
    )
    return GenerationContext(prompt_values=values, validation=validation)
