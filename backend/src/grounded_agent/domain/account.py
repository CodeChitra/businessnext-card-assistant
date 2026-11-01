from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict

CardProduct = Literal["Classic", "Signature"]
KycRiskBand = Literal["low", "medium", "high"]


class Account(BaseModel):
    """One customer record from accounts.json. Field names mirror the source exactly."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    customer_id: str
    name: str
    card_product: CardProduct
    current_limit: int
    statement_balance: int
    minimum_due: int
    due_date: date
    card_year_spend: int
    open_dispute: bool
    vulnerable_flag: bool
    last_limit_increase_date: date | None
    kyc_last_done: date
    kyc_risk_band: KycRiskBand
    months_repayment_history: int
    avg_utilisation_3m: float
    behavioural_score: int
