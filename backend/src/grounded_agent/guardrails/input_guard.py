"""Inspect the customer's message before anything else runs.

Flags are passed downstream (the generator sees them; the graph short-circuits on a
request for another customer's data). Identity always comes from the session, never from
ids or names in the message.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from grounded_agent.retrieval.sanitizer import is_instruction_like

_CUSTOMER_ID = re.compile(r"\bCUST-\d{4}\b", re.IGNORECASE)
_INJECTION = (
    re.compile(
        r"\bignore (all |any |your |the )?(previous |prior )?(instructions|rules|polic)", re.I
    ),
    re.compile(r"\bdo (what|as) (it|they|the notes?|the note) says?\b", re.I),
    re.compile(r"\b(pretend|act as|you are now|developer mode|jailbreak)\b", re.I),
    re.compile(r"\b(system|hidden) prompt\b", re.I),
)


@dataclass(frozen=True)
class InputFlags:
    injection_suspected: bool = False
    other_customer_ids: tuple[str, ...] = ()

    def describe(self) -> str:
        parts = []
        if self.injection_suspected:
            parts.append("possible instruction injection in the customer message")
        if self.other_customer_ids:
            parts.append("references another customer's id")
        return "; ".join(parts) or "none"


def inspect_input(message: str, session_customer_id: str) -> InputFlags:
    others = sorted(
        {m.upper() for m in _CUSTOMER_ID.findall(message)} - {session_customer_id.upper()}
    )
    injection = is_instruction_like(message) or any(p.search(message) for p in _INJECTION)
    return InputFlags(injection_suspected=injection, other_customer_ids=tuple(others))
