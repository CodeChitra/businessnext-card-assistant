from __future__ import annotations

import asyncio
from typing import Any

from grounded_agent.domain.errors import CustomerNotFound, UpstreamTimeout
from grounded_agent.repositories.base import AccountRepository
from grounded_agent.tools.faults import FaultInjector


class AccountStateTool:
    """get_account_state(customer_id) -> dict, per the fixed contract in data/tools.md.

    Raises CustomerNotFound for an unknown id and UpstreamTimeout ~1 call in 12.
    Retries and the degraded-mode UX are the agent's job, not the tool's.
    """

    name = "get_account_state"

    def __init__(
        self,
        repository: AccountRepository,
        faults: FaultInjector,
        latency_ms: int = 400,
    ) -> None:
        self._repository = repository
        self._faults = faults
        self._latency_s = latency_ms / 1000

    async def get_account_state(self, customer_id: str) -> dict[str, Any]:
        await asyncio.sleep(self._latency_s)
        if self._faults.should_timeout():
            raise UpstreamTimeout(self.name)
        account = self._repository.get(customer_id)
        if account is None:
            raise CustomerNotFound(customer_id)
        return account.model_dump(mode="json")
