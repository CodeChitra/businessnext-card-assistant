from __future__ import annotations

from datetime import date

import pytest

from grounded_agent.config.settings import Settings
from grounded_agent.policy.fees import format_inr, load_waiver_thresholds, parse_waiver_thresholds
from grounded_agent.policy.rules import PolicyEngine, kyc_status
from grounded_agent.repositories.json_account_repository import JsonAccountRepository

AS_OF = date(2026, 8, 25)


@pytest.fixture
def engine(settings: Settings) -> PolicyEngine:
    return PolicyEngine(load_waiver_thresholds(settings.corpus_dir))


@pytest.fixture
def repo(settings: Settings) -> JsonAccountRepository:
    return JsonAccountRepository(settings.accounts_path)


def assess(
    engine: PolicyEngine,
    repo: JsonAccountRepository,
    cid: str,
    intent: str = "limit_increase",
    today: date = AS_OF,
):  # type: ignore[no-untyped-def]
    return engine.assess(repo.get(cid), intent, today)  # type: ignore[arg-type]


def test_waiver_thresholds_come_from_the_fee_policy(settings: Settings) -> None:
    assert load_waiver_thresholds(settings.corpus_dir) == {"Classic": 150000, "Signature": 400000}
    with pytest.raises(ValueError):
        parse_waiver_thresholds("no table")


@pytest.mark.parametrize(
    ("n", "s"), [(162000, "1,62,000"), (400000, "4,00,000"), (500, "500"), (1250000, "12,50,000")]
)
def test_indian_grouping(n: int, s: str) -> None:
    assert format_inr(n) == s


def test_ev001_fee_waiver_not_met_states_both_figures(engine, repo) -> None:  # type: ignore[no-untyped-def]
    a = assess(engine, repo, "CUST-2000", "fee")
    finding = next(f for f in a.findings if f.rule_id.startswith("FEE_WAIVER"))
    assert finding.rule_id == "FEE_WAIVER_NOT_MET"
    assert "1,62,000" in finding.customer_reason and "4,00,000" in finding.customer_reason
    assert a.decision == "none"


def test_classic_waiver_met(engine, repo) -> None:  # type: ignore[no-untyped-def]
    assert "FEE_WAIVER_MET" in assess(engine, repo, "CUST-2004", "fee").rules_fired


def test_ev002_open_dispute_is_a_mandatory_decline(engine, repo) -> None:  # type: ignore[no-untyped-def]
    a = assess(engine, repo, "CUST-2003")
    assert a.decision == "decline" and a.reason_codes == ["AA04"]
    assert "POL-SVC-005#body" in a.pinned_chunks


def test_ev003_vulnerable_declines_and_suppresses_sales(engine, repo) -> None:  # type: ignore[no-untyped-def]
    a = assess(engine, repo, "CUST-2006")
    assert a.decision == "decline" and a.suppress_sales
    assert "DECLINE_VULNERABLE" in a.rules_fired
    assert "POL-CON-004#body" in a.pinned_chunks


def test_vulnerable_suppresses_sales_for_any_intent(engine, repo) -> None:  # type: ignore[no-untyped-def]
    assert assess(engine, repo, "CUST-2006", "product_terms").suppress_sales


def test_ev004_six_month_bar_from_crd001_not_three_from_crd011(engine, repo) -> None:  # type: ignore[no-untyped-def]
    a = assess(engine, repo, "CUST-2001")  # increased 2026-06-19
    assert a.decision == "decline" and a.reason_codes == ["AA05"]
    # 4 months later: past CRD-011's 3 months but inside CRD-001's 6 -> still declined
    assert assess(engine, repo, "CUST-2001", today=date(2026, 10, 25)).reason_codes == ["AA05"]
    # after 6 months the bar lifts (util 0.25 < 40% then routes to a human review)
    later = assess(engine, repo, "CUST-2001", today=date(2026, 12, 20))
    assert later.decision == "refer" and "DECLINE_RECENT_INCREASE" not in later.rules_fired


def test_ev005_thin_file_is_referred_with_cap(engine, repo) -> None:  # type: ignore[no-untyped-def]
    a = assess(engine, repo, "CUST-2005")
    assert a.decision == "refer" and a.rules_fired == ["REFER_THIN_FILE"]
    assert any("1,50,000" in fact for fact in a.facts)  # 1.25 x 1,20,000
    assert "POL-CRD-003#5" in a.pinned_chunks


def test_ev006_overdue_rekyc_declines_but_does_not_freeze(engine, repo, settings: Settings) -> None:  # type: ignore[no-untyped-def]
    acct = repo.get("CUST-2008")
    assert acct is not None
    due, overdue = kyc_status(acct, AS_OF)
    assert due == date(2018, 4, 2) and overdue > 90
    a = assess(engine, repo, "CUST-2008")
    assert a.decision == "decline" and a.reason_codes == ["AA06"]
    info = next(f for f in a.findings if f.rule_id == "KYC_OVERDUE")
    assert "not frozen" in info.customer_reason


def test_no_mandatory_decline_still_never_approves(engine, repo) -> None:  # type: ignore[no-untyped-def]
    a = assess(engine, repo, "CUST-2000")
    assert a.decision == "refer" and a.rules_fired == ["REFER_INCOME_ASSESSMENT"]


def test_score_shortfall_is_referred_not_auto_declined(engine, repo) -> None:  # type: ignore[no-untyped-def]
    a = assess(engine, repo, "CUST-2004")  # score 590 < 620
    assert a.decision == "refer" and a.rules_fired == ["REFER_ELIGIBILITY_REVIEW"]
    assert all("590" not in f.customer_reason for f in a.findings)


def test_no_account_means_no_account_rules(engine) -> None:  # type: ignore[no-untyped-def]
    assert engine.assess(None, "limit_increase", AS_OF).decision == "none"
