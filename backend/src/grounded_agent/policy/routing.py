"""Queue catalogue parsed from POL-SVC-006, so routing follows the governed document."""

from __future__ import annotations

import re
from pathlib import Path

from grounded_agent.domain.service_request import QueueSpec

ROUTING_DOC_GLOB = "POL-SVC-006*.md"
FALLBACK_QUEUE = "GENERAL"

# "- Transaction dispute -> DISPUTES, SLA 2 working days"
_QUEUE_LINE = re.compile(
    r"^-\s*(?P<intent>.+?)\s*->\s*(?P<queue>[A-Z_]+),"
    r"\s*SLA\s+(?P<n>\d+)\s+(?P<unit>hours?|working days?)",
)
# "... is routed to GENERAL and must be reviewed by a human within 1 working day."
_FALLBACK_LINE = re.compile(
    r"routed to (?P<queue>[A-Z_]+).*?within (?P<n>\d+) (?P<unit>hours?|working days?)",
    re.DOTALL,
)


def _to_hours(n: int, unit: str, working_hours_per_day: int) -> int:
    return n if unit.startswith("hour") else n * working_hours_per_day


def parse_queue_catalog(text: str, working_hours_per_day: int) -> dict[str, QueueSpec]:
    queues: dict[str, QueueSpec] = {}
    for line in text.splitlines():
        m = _QUEUE_LINE.match(line.strip())
        if m:
            n, unit = int(m["n"]), m["unit"]
            queues[m["queue"]] = QueueSpec(
                queue=m["queue"],
                intent=m["intent"],
                sla_hours=_to_hours(n, unit, working_hours_per_day),
                sla_text=f"{n} {unit}",
            )
    fb = _FALLBACK_LINE.search(text)
    if fb:
        n, unit = int(fb["n"]), fb["unit"]
        queues[fb["queue"]] = QueueSpec(
            queue=fb["queue"],
            intent="Cannot be categorised with confidence",
            sla_hours=_to_hours(n, unit, working_hours_per_day),
            sla_text=f"{n} {unit}",
        )
    if FALLBACK_QUEUE not in queues or len(queues) < 2:
        raise ValueError("POL-SVC-006 could not be parsed into a queue catalogue")
    return queues


def load_queue_catalog(corpus_dir: Path, working_hours_per_day: int) -> dict[str, QueueSpec]:
    matches = sorted(corpus_dir.glob(ROUTING_DOC_GLOB))
    if not matches:
        raise FileNotFoundError(f"Routing policy {ROUTING_DOC_GLOB} not found in {corpus_dir}")
    return parse_queue_catalog(matches[0].read_text(encoding="utf-8"), working_hours_per_day)
