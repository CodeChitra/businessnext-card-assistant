"""Sanitise the model's suggested next questions before the customer sees them.

Follow-ups are not claims, so they are not citation-checked; instead they are kept harmless:
short customer-voice questions with no numbers (nothing to ground), no sales wording for
suppressed customers, no conduct flags and no internal ids or score talk. A bad suggestion is
dropped silently. It must never force a repair of an otherwise good answer.
"""

from __future__ import annotations

import re

from grounded_agent.guardrails.output_guard import discloses_vulnerability, has_sales_content

MAX_FOLLOW_UPS = 3
MIN_CHARS, MAX_CHARS = 8, 90

_LEADING_LIST_MARK = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")
_INTERNAL = re.compile(r"\bPOL-|\b(chunk|rule)[ _.#]|\bscore\b|\bAA0\d\b", re.IGNORECASE)


def _tidy(text: str) -> str:
    return " ".join(_LEADING_LIST_MARK.sub("", text).split())


def clean_follow_ups(candidates: list[str], *, suppress_sales: bool, asked: str = "") -> list[str]:
    """Up to three distinct, safe questions. `asked` is the question just answered."""
    seen = {_tidy(asked).casefold()}
    kept: list[str] = []
    for raw in candidates:
        text = _tidy(raw)
        key = text.casefold()
        if (
            not text.endswith("?")
            or not MIN_CHARS <= len(text) <= MAX_CHARS
            or any(ch.isdigit() for ch in text)
            or _INTERNAL.search(text)
            or discloses_vulnerability(text)
            or (suppress_sales and has_sales_content(text))
            or key in seen
        ):
            continue
        seen.add(key)
        kept.append(text)
        if len(kept) == MAX_FOLLOW_UPS:
            break
    return kept


# Always-safe starters for turns where the model offered none (greetings, out-of-scope, refusals):
# no sales wording, no limit-increase prompt (a vulnerable customer is always declined), and
# nothing that needs the account (they must also work when it is unavailable).
STARTERS: tuple[str, ...] = (
    "What is my current credit limit?",
    "What fees apply to my card?",
    "How do I report a payment I don't recognise?",
)


def starter_follow_ups() -> list[str]:
    return list(STARTERS)
