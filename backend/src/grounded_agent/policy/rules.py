"""Deterministic policy rules. The LLM explains these outcomes; it never makes them.

Every finding carries the chunk ids (and account fields) that justify it, which are pinned
into the generator's context, so grounding that depends on account state (e.g. an overdue
re-KYC) never relies on retrieval luck.

Limit-increase decision order:
  1. Any mandatory decline (CRD-001 s.3, CON-004, KYC-008, SVC-005) -> decline.
  2. Thin file (CRD-003 s.5) -> refer to a credit officer, cap 1.25x.
  3. Eligibility not met (CRD-001 s.1) -> refer. GOV-009 requires an approved reason code
     and none fits a score or utilisation shortfall, so the agent cannot issue a compliant
     automated decline; a human must.
  4. Otherwise -> refer: income and debt-burden (CRD-001 s.2-3) are not in our data.
The agent never approves.
"""

from __future__ import annotations

import calendar
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict

from grounded_agent.domain.account import Account
from grounded_agent.domain.response import Intent, ReasonCode
from grounded_agent.policy.fees import format_inr

Outcome = Literal["mandatory_decline", "not_eligible", "refer", "info"]
Decision = Literal["decline", "refer", "none"]

MIN_SCORE = 620  # CRD-001 s.1
MIN_UTILISATION = 0.40  # CRD-001 s.1
MIN_HISTORY_MONTHS = 6  # CRD-001 s.1 (statement cycles) / CRD-003 s.5 (thin file)
INCREASE_BAR_MONTHS = 6  # CRD-001 s.3 (prevails over CRD-011)
THIN_FILE_CAP = 1.25  # CRD-003 s.5
KYC_CYCLE_YEARS = {"high": 2, "medium": 8, "low": 10}  # KYC-008
KYC_GRACE_DAYS = 90  # KYC-008


class RuleFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    rule_id: str
    outcome: Outcome
    customer_reason: str  # safe to say to the customer; never contains score values
    reason_code: ReasonCode | None = None
    citations: tuple[str, ...] = ()
    facts: tuple[str, ...] = ()  # computed values the generator may quote


class PolicyAssessment(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision: Decision
    findings: tuple[RuleFinding, ...] = ()
    suppress_sales: bool = False

    @property
    def reason_codes(self) -> list[ReasonCode]:
        return sorted(
            {
                f.reason_code
                for f in self.findings
                if f.reason_code and f.outcome == "mandatory_decline"
            }
        )

    @property
    def pinned_chunks(self) -> list[str]:
        return sorted({c for f in self.findings for c in f.citations if c.startswith("POL-")})

    @property
    def rules_fired(self) -> list[str]:
        return [f.rule_id for f in self.findings]

    @property
    def facts(self) -> list[str]:
        return [fact for f in self.findings for fact in f.facts]


def _add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    year, month = d.year + y, m + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def kyc_status(account: Account, today: date) -> tuple[date, int]:
    """(due date, days overdue; negative means not yet due)."""
    due = _add_months(account.kyc_last_done, 12 * KYC_CYCLE_YEARS[account.kyc_risk_band])
    return due, (today - due).days


class PolicyEngine:
    def __init__(self, waiver_thresholds: dict[str, int]) -> None:
        self._waivers = waiver_thresholds

    def assess(self, account: Account | None, intent: Intent, today: date) -> PolicyAssessment:
        if account is None:  # degraded mode: no account-based rules can run
            return PolicyAssessment(decision="none")

        findings: list[RuleFinding] = []
        findings += self._standing_flags(account, today)
        if intent == "fee":
            findings += self._fee_waiver(account)
        if intent == "limit_increase":
            findings += self._limit_increase(account, today)

        decision: Decision = "none"
        if intent == "limit_increase":
            if any(f.outcome == "mandatory_decline" for f in findings):
                decision = "decline"
            else:
                decision = "refer"
        return PolicyAssessment(
            decision=decision,
            findings=tuple(findings),
            suppress_sales=account.vulnerable_flag,
        )

    # --- rule groups ---------------------------------------------------------------------

    def _standing_flags(self, a: Account, today: date) -> list[RuleFinding]:
        out: list[RuleFinding] = []
        if a.vulnerable_flag:
            out.append(
                RuleFinding(
                    rule_id="CONDUCT_VULNERABLE_NO_SALES",
                    outcome="info",
                    customer_reason="",  # never surfaced; it only suppresses sales content
                    citations=("POL-CON-004#body",),
                )
            )
        due, overdue = kyc_status(a, today)
        if overdue > KYC_GRACE_DAYS:
            out.append(
                RuleFinding(
                    rule_id="KYC_OVERDUE",
                    outcome="info",
                    customer_reason=(
                        "Some of the information we hold needs to be refreshed (periodic KYC). "
                        "Your account is not frozen because of this, and existing limits are "
                        "unaffected."
                    ),
                    reason_code="AA06",
                    citations=(
                        "POL-KYC-008#body",
                        "account.kyc_last_done",
                        "account.kyc_risk_band",
                    ),
                    facts=(f"re-KYC was due on {due.isoformat()} ({overdue} days overdue)",),
                )
            )
        return out

    def _fee_waiver(self, a: Account) -> list[RuleFinding]:
        threshold = self._waivers.get(a.card_product)
        if threshold is None:
            return []
        met = a.card_year_spend >= threshold
        spend, limit = format_inr(a.card_year_spend), format_inr(threshold)
        reason = (
            f"Your card-year spend is {spend}. The {a.card_product} annual fee is waived at "
            f"{limit}, so "
            + (
                "the waiver applies."
                if met
                else "the waiver threshold was not met and the fee applies."
            )
        )
        return [
            RuleFinding(
                rule_id="FEE_WAIVER_MET" if met else "FEE_WAIVER_NOT_MET",
                outcome="info",
                customer_reason=reason,
                citations=("POL-FEE-007#body", "account.card_year_spend", "account.card_product"),
                facts=(
                    f"card_year_spend={spend}",
                    f"waiver_threshold={limit}",
                    f"waiver_met={met}",
                ),
            )
        ]

    def _limit_increase(self, a: Account, today: date) -> list[RuleFinding]:
        out: list[RuleFinding] = []

        # 1. Mandatory declines (CRD-001 s.3 and the policies it references)
        if a.open_dispute:
            out.append(
                RuleFinding(
                    rule_id="DECLINE_OPEN_DISPUTE",
                    outcome="mandatory_decline",
                    customer_reason="There is an open dispute on your account.",
                    reason_code="AA04",
                    citations=("POL-CRD-001#3", "POL-SVC-005#body", "account.open_dispute"),
                )
            )
        if a.vulnerable_flag:
            out.append(
                RuleFinding(
                    rule_id="DECLINE_VULNERABLE",
                    outcome="mandatory_decline",
                    customer_reason="We are not able to offer a limit increase at this time.",
                    citations=("POL-CRD-001#3", "POL-CON-004#body"),
                )
            )
        if a.last_limit_increase_date is not None:
            bar_ends = _add_months(a.last_limit_increase_date, INCREASE_BAR_MONTHS)
            if today < bar_ends:
                out.append(
                    RuleFinding(
                        rule_id="DECLINE_RECENT_INCREASE",
                        outcome="mandatory_decline",
                        customer_reason=(
                            "Your limit was increased recently; a further increase cannot be "
                            "considered within 6 months of the previous one."
                        ),
                        reason_code="AA05",
                        citations=("POL-CRD-001#3", "account.last_limit_increase_date"),
                        facts=(
                            f"last increase {a.last_limit_increase_date.isoformat()}; "
                            f"earliest next review {bar_ends.isoformat()}",
                        ),
                    )
                )
        _, overdue = kyc_status(a, today)
        if overdue > KYC_GRACE_DAYS:
            out.append(
                RuleFinding(
                    rule_id="DECLINE_KYC_OVERDUE",
                    outcome="mandatory_decline",
                    customer_reason=(
                        "Some of the information we hold needs to be refreshed before your limit "
                        "can be increased."
                    ),
                    reason_code="AA06",
                    citations=("POL-KYC-008#body", "account.kyc_last_done"),
                )
            )
        if any(f.outcome == "mandatory_decline" for f in out):
            return out

        # 2. Thin file: eligible but capped and referred (CRD-003 s.5)
        if a.months_repayment_history < MIN_HISTORY_MONTHS:
            cap = round(a.current_limit * THIN_FILE_CAP)
            out.append(
                RuleFinding(
                    rule_id="REFER_THIN_FILE",
                    outcome="refer",
                    customer_reason=(
                        "Because your repayment history with us is short, any increase is capped "
                        "at 1.25 times your current limit and is reviewed by a credit officer."
                    ),
                    reason_code="AA03",
                    citations=(
                        "POL-CRD-003#5",
                        "account.months_repayment_history",
                        "account.current_limit",
                    ),
                    facts=(f"maximum revised limit {format_inr(cap)}",),
                )
            )
            return out

        # 3. Eligibility shortfalls: no approved reason code fits, so a human decides.
        if a.behavioural_score < MIN_SCORE or a.avg_utilisation_3m < MIN_UTILISATION:
            out.append(
                RuleFinding(
                    rule_id="REFER_ELIGIBILITY_REVIEW",
                    outcome="not_eligible",
                    customer_reason=(
                        "Your request needs a review by our credit team before a decision can "
                        "be made."
                    ),
                    citations=("POL-CRD-001#1", "POL-GOV-009#body"),
                )
            )
            return out

        # 4. No rule blocks it, but income / debt-burden are unknown to us.
        out.append(
            RuleFinding(
                rule_id="REFER_INCOME_ASSESSMENT",
                outcome="refer",
                customer_reason=(
                    "Your request can be considered, but it needs an income assessment by our "
                    "credit team before any decision."
                ),
                citations=("POL-CRD-001#2", "POL-CRD-002#body"),
            )
        )
        return out
