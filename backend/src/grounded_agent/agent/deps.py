from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from grounded_agent.domain.service_request import QueueSpec
from grounded_agent.llm.structured import StructuredLLM
from grounded_agent.observability.metrics import PriceTable
from grounded_agent.policy.rules import PolicyEngine
from grounded_agent.prompts.registry import PromptRegistry
from grounded_agent.retrieval.base import Retriever
from grounded_agent.retrieval.hybrid import HybridRetriever
from grounded_agent.tools.account_state import AccountStateTool
from grounded_agent.tools.service_request import ServiceRequestTool


@dataclass(frozen=True)
class RetryPolicy:
    attempts: int = 3  # 1 call + 2 retries
    per_attempt_timeout_s: float = 2.0
    backoff_base_s: float = 0.1


@dataclass
class AgentDeps:
    """Everything nodes need, wired once in bootstrap.py (the composition root)."""

    account_tool: AccountStateTool
    service_tool: ServiceRequestTool
    retriever: Retriever
    chunk_index: HybridRetriever  # id -> chunk lookup for rule-pinned chunks
    policy: PolicyEngine
    llm: StructuredLLM
    prompts: PromptRegistry
    queues: dict[str, QueueSpec]
    prices: PriceTable
    today: date
    retry: RetryPolicy = RetryPolicy()
