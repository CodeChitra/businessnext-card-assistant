from __future__ import annotations

import json
from pathlib import Path

from grounded_agent.domain.account import Account


class JsonAccountRepository:
    """Loads accounts.json once; records are immutable after load."""

    def __init__(self, path: Path) -> None:
        raw: dict[str, dict[str, object]] = json.loads(path.read_text(encoding="utf-8"))
        self._accounts = {cid: Account.model_validate(rec) for cid, rec in raw.items()}

    def get(self, customer_id: str) -> Account | None:
        return self._accounts.get(customer_id)

    def list_ids(self) -> list[str]:
        return sorted(self._accounts)
