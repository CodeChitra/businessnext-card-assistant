from __future__ import annotations

from typing import Protocol

from grounded_agent.domain.account import Account


class AccountRepository(Protocol):
    """Source of account records. Only the account-state tool talks to this."""

    def get(self, customer_id: str) -> Account | None: ...

    def list_ids(self) -> list[str]: ...
