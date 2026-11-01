"""Token and cost accounting per request."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import yaml

from grounded_agent.llm.structured import LLMCall

PRICING_PATH = Path(__file__).resolve().parents[1] / "config" / "pricing.yaml"


class PriceTable:
    def __init__(self, path: Path = PRICING_PATH) -> None:
        raw: dict[str, dict[str, float]] = yaml.safe_load(path.read_text()) or {}
        self._prices = raw

    def cost(self, call: LLMCall) -> float | None:
        name = call.model.split(":", 1)[-1]
        price = self._prices.get(name)
        if price is None:
            return None
        return (call.input_tokens * price["input"] + call.output_tokens * price["output"]) / 1e6


def summarise_calls(calls: Iterable[LLMCall], prices: PriceTable) -> dict[str, object]:
    calls = list(calls)
    costs = [prices.cost(c) for c in calls]
    return {
        "input_tokens": sum(c.input_tokens for c in calls),
        "output_tokens": sum(c.output_tokens for c in calls),
        "cost_usd": round(sum(c for c in costs if c is not None), 6),
        "unpriced_models": sorted(
            {c.model for c, p in zip(calls, costs, strict=True) if p is None}
        ),
        "fallback_used": any(c.fallback_used for c in calls),
        "models": sorted({c.model for c in calls}),
    }
