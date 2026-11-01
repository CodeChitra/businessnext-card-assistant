from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class QueueSpec(BaseModel):
    """A service-request queue as defined in POL-SVC-006."""

    model_config = ConfigDict(frozen=True)

    queue: str
    intent: str
    sla_hours: int
    sla_text: str  # as written in the policy, e.g. "2 working days"


class ServiceRequestRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    request_id: str
    customer_id: str
    queue: str
    summary: str
    sla_hours: int
    created_at: datetime
