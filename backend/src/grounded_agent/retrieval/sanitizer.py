"""Ingestion-time defences against content that should not be treated as policy.

1. Trust classification: drafts and documents that declare themselves "not policy" can never
   ground a policy claim (POL-OPS-012 is the supplied example).
2. Instruction stripping: lines that address the model rather than describe policy are
   quarantined from every document, trusted or not. This is defence in depth: the
   citation validator and the rules engine are the controls that actually hold.
"""

from __future__ import annotations

import re

from grounded_agent.domain.policy import Trust

_DRAFT_VERSION = re.compile(r"\bdraft\b", re.IGNORECASE)
_SELF_DECLARED_NON_POLICY = re.compile(r"\bnot policy\b", re.IGNORECASE)

_INSTRUCTION_PATTERNS = (
    re.compile(r"\b(system|developer)\s+(note|prompt|message|instruction)s?\b", re.IGNORECASE),
    re.compile(r"\b(automated|ai)\s+assistants?\b", re.IGNORECASE),
    re.compile(
        r"\b(disregard|ignore|override)\b.{0,40}\b(instruction|rule|polic|citation)", re.IGNORECASE
    ),
    re.compile(r"\bdo not (mention|reveal|disclose) this\b", re.IGNORECASE),
    re.compile(r"\byou (must|should) now\b", re.IGNORECASE),
)


def classify_trust(version: str, body: str) -> Trust:
    # "Draft" is only meaningful in the version field; "not policy" only near the top.
    if _DRAFT_VERSION.search(version) or _SELF_DECLARED_NON_POLICY.search(body[:400]):
        return Trust.NON_POLICY
    return Trust.POLICY


def is_instruction_like(line: str) -> bool:
    return any(p.search(line) for p in _INSTRUCTION_PATTERNS)


def strip_instructions(body: str) -> tuple[str, tuple[str, ...]]:
    """Remove instruction-like list items or paragraphs. Returns (clean_body, removed)."""
    kept: list[str] = []
    removed: list[str] = []
    # Group continuation lines with their bullet so a multi-line injection is removed whole.
    blocks: list[list[str]] = []
    for line in body.splitlines():
        starts_block = (
            line.lstrip().startswith(("- ", "* ")) or not line.strip() or line.startswith("#")
        )
        if starts_block or not blocks:
            blocks.append([line])
        else:
            blocks[-1].append(line)
    for block in blocks:
        text = " ".join(part.strip() for part in block)
        if text and is_instruction_like(text):
            removed.append(text)
        else:
            kept.extend(block)
    return "\n".join(kept), tuple(removed)
