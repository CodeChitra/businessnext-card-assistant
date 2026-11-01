from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from grounded_agent.agent.state import Simulate


class ChatRequest(BaseModel):
    # In production this comes from the authenticated session, never from the client body.
    customer_id: str = Field(pattern=r"^CUST-\d{4}$", examples=["CUST-2007"])
    message: str = Field(min_length=1, max_length=2000)
    thread_id: str | None = Field(default=None, max_length=64)
    rewind_to: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Edit or replay: continue `thread_id` from a fork that keeps only its first "
        "N completed customer turns. The response's `meta.thread_id` is the new thread.",
    )
    simulate: Simulate | None = Field(
        default=None, description="Demo only (DEMO_FAULTS=true): force a failure path."
    )


class CustomerSummary(BaseModel):
    customer_id: str
    name: str
    card_product: str


class PolicyChunkView(BaseModel):
    chunk_id: str
    doc_id: str
    title: str
    heading: str | None
    section: str
    version: str
    effective_date: str | None
    trust: Literal["policy", "non_policy"]
    text: str


class HealthView(BaseModel):
    status: Literal["ok"]
    as_of_date: str
    chunks_indexed: int
    models: dict[str, str | None]
    prompt_versions: dict[str, str]
    tracing: dict[str, object]
    demo_faults: bool


class ErrorView(BaseModel):
    error: str
    detail: str | None = None
