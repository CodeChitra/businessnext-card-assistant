"""Known conflicts between governed documents and which one prevails.

Hand-maintained on purpose: the corpus itself states the resolution (POL-CRD-011 defers to
POL-CRD-001 s.3). At scale this becomes an ingestion-time contradiction check with an owner
sign-off (docs/scaling.md).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Precedence:
    topic: str
    superseded_doc: str
    prevailing_chunk: str
    note: str


PRECEDENCE: tuple[Precedence, ...] = (
    Precedence(
        topic="minimum gap between limit increases",
        superseded_doc="POL-CRD-011",
        prevailing_chunk="POL-CRD-001#3",
        note=(
            "POL-CRD-011 mentions 3 months between increases, but POL-CRD-001 Section 3 "
            "(6 months) prevails where the two conflict. Never state 3 months as the rule."
        ),
    ),
)


def notes_for(doc_ids: set[str]) -> list[Precedence]:
    return [p for p in PRECEDENCE if p.superseded_doc in doc_ids]
