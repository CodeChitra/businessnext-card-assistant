"""Enforces the citation contract (SPEC 6.2) on a DraftResponse.

1. answer / decline / raise_request carry at least one claim; every claim has a citation.
2. A policy citation must be a trusted chunk that is in this turn's context (retrieved or
   pinned by a rule). Non-policy chunks (POL-OPS-012) can never back a claim.
3. An account citation must name a fetched, non-internal field; none are allowed in
   degraded mode. A `rule.<ID>` citation must be a rule outcome of this turn (computed
   values such as a capped limit or the next review date are grounded this way).
4. Every number in the message must appear in a cited source or in rule-computed facts.
   A refusal with no claims therefore cannot state any figure.

What it cannot do: judge whether a valid citation actually supports its claim. That is
measured offline (Faithfulness), and is listed in the README under "what not to trust".
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from grounded_agent.domain.response import ACCOUNT_PREFIX, RULE_PREFIX, DraftResponse
from grounded_agent.guardrails.numbers import numbers_in

# Never cited and never shown to the model (SPEC: scores are not disclosed).
INTERNAL_ACCOUNT_FIELDS = frozenset({"behavioural_score"})


@dataclass(frozen=True)
class ValidationContext:
    policy_chunks: Mapping[str, str]  # trusted chunk id -> text
    untrusted_chunk_ids: frozenset[str] = frozenset()
    account: Mapping[str, Any] | None = None  # None = degraded mode
    rule_texts: Mapping[str, str] = field(default_factory=dict)  # "rule.<ID>" -> reason + facts
    extra_grounded_text: tuple[str, ...] = field(default_factory=tuple)


def validate_citations(draft: DraftResponse, ctx: ValidationContext) -> list[str]:
    errors: list[str] = []
    if draft.behaviour != "refuse" and not draft.claims:
        errors.append(f"behaviour '{draft.behaviour}' requires at least one cited claim")

    grounded_text: list[str] = list(ctx.extra_grounded_text)
    for i, claim in enumerate(draft.claims, start=1):
        if not claim.citations:
            errors.append(f"claim {i} has no citation: {claim.text!r}")
        for ref in claim.citations:
            if ref.startswith(ACCOUNT_PREFIX):
                fld = ref.removeprefix(ACCOUNT_PREFIX)
                if ctx.account is None:
                    errors.append(f"claim {i} cites {ref} but account data is unavailable")
                elif fld in INTERNAL_ACCOUNT_FIELDS or fld not in ctx.account:
                    errors.append(f"claim {i} cites unknown or internal account field {ref}")
                else:
                    grounded_text.append(f"{fld} {ctx.account[fld]}")
            elif ref.startswith(RULE_PREFIX):
                if ref not in ctx.rule_texts:
                    errors.append(
                        f"claim {i} cites {ref}, which is not a rule outcome of this turn"
                    )
                else:
                    grounded_text.append(ctx.rule_texts[ref])
            elif ref in ctx.untrusted_chunk_ids:
                errors.append(
                    f"claim {i} cites {ref}, which is not policy and cannot ground a claim"
                )
            elif ref not in ctx.policy_chunks:
                errors.append(f"claim {i} cites {ref}, which is not in the provided context")
            else:
                grounded_text.append(ctx.policy_chunks[ref])

    allowed = numbers_in("\n".join(grounded_text))
    ungrounded = sorted(numbers_in(draft.message) - allowed)
    if ungrounded:
        errors.append(
            f"message states numbers not found in any cited source: {', '.join(ungrounded)}"
        )
    return errors
