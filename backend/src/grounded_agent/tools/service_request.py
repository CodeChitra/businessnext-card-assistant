from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from grounded_agent.domain.errors import InvalidCategory
from grounded_agent.domain.service_request import QueueSpec, ServiceRequestRecord


class ServiceRequestTool:
    """raise_service_request(customer_id, category, summary) -> dict, per data/tools.md.

    `category` must exactly match a queue named in POL-SVC-006. Anything else raises
    InvalidCategory: the tool never guesses, the caller decides to fall back to GENERAL.
    """

    name = "raise_service_request"

    def __init__(self, queues: Mapping[str, QueueSpec]) -> None:
        self._queues = dict(queues)
        self._records: list[ServiceRequestRecord] = []

    @property
    def categories(self) -> list[str]:
        return sorted(self._queues)

    async def raise_service_request(
        self, customer_id: str, category: str, summary: str
    ) -> dict[str, Any]:
        spec = self._queues.get(category)
        if spec is None:
            raise InvalidCategory(category, self.categories)
        if not summary.strip():
            raise ValueError("summary must not be empty")
        record = ServiceRequestRecord(
            request_id=f"SR-{uuid.uuid4().hex[:8].upper()}",
            customer_id=customer_id,
            queue=spec.queue,
            summary=summary.strip(),
            sla_hours=spec.sla_hours,
            created_at=datetime.now(UTC),
        )
        self._records.append(record)
        return {
            "request_id": record.request_id,
            "queue": record.queue,
            "sla_hours": record.sla_hours,
        }

    def records(self) -> list[ServiceRequestRecord]:
        return list(self._records)
