from __future__ import annotations

import asyncio

import pytest

from grounded_agent.config.settings import Settings
from grounded_agent.domain.errors import CustomerNotFound, InvalidCategory, UpstreamTimeout
from grounded_agent.policy.routing import load_queue_catalog, parse_queue_catalog
from grounded_agent.repositories.json_account_repository import JsonAccountRepository
from grounded_agent.tools.account_state import AccountStateTool
from grounded_agent.tools.faults import FaultInjector, force_timeout
from grounded_agent.tools.service_request import ServiceRequestTool


@pytest.fixture
def repo(settings: Settings) -> JsonAccountRepository:
    return JsonAccountRepository(settings.accounts_path)


def no_faults() -> FaultInjector:
    return FaultInjector(timeout_rate=0.0)


# --- get_account_state ---------------------------------------------------------------


def test_repository_loads_ten_typed_customers(repo: JsonAccountRepository) -> None:
    assert len(repo.list_ids()) == 10
    acct = repo.get("CUST-2001")
    assert acct is not None and str(acct.last_limit_increase_date) == "2026-06-19"


async def test_returns_the_record_as_a_dict(repo: JsonAccountRepository) -> None:
    tool = AccountStateTool(repo, no_faults(), latency_ms=0)
    state = await tool.get_account_state("CUST-2003")
    assert state["customer_id"] == "CUST-2003"
    assert state["open_dispute"] is True
    assert state["due_date"] == "2026-09-08"


async def test_unknown_customer_raises(repo: JsonAccountRepository) -> None:
    with pytest.raises(CustomerNotFound):
        await AccountStateTool(repo, no_faults(), latency_ms=0).get_account_state("CUST-9999")


async def test_forced_timeout_is_scoped_to_the_context(repo: JsonAccountRepository) -> None:
    tool = AccountStateTool(repo, no_faults(), latency_ms=0)
    with force_timeout(), pytest.raises(UpstreamTimeout):
        await tool.get_account_state("CUST-2000")
    assert (await tool.get_account_state("CUST-2000"))["customer_id"] == "CUST-2000"


async def test_timeout_rate_is_roughly_one_in_twelve(repo: JsonAccountRepository) -> None:
    tool = AccountStateTool(repo, FaultInjector(1 / 12, seed=7), latency_ms=0)
    failures = 0
    for _ in range(1200):
        try:
            await tool.get_account_state("CUST-2000")
        except UpstreamTimeout:
            failures += 1
    assert 60 <= failures <= 140


async def test_seeded_faults_are_reproducible(repo: JsonAccountRepository) -> None:
    async def pattern(seed: int) -> list[bool]:
        tool = AccountStateTool(repo, FaultInjector(0.3, seed=seed), latency_ms=0)
        out = []
        for _ in range(30):
            try:
                await tool.get_account_state("CUST-2000")
                out.append(False)
            except UpstreamTimeout:
                out.append(True)
        return out

    assert await pattern(42) == await pattern(42)


async def test_simulated_latency_is_applied(repo: JsonAccountRepository) -> None:
    tool = AccountStateTool(repo, no_faults(), latency_ms=50)
    loop = asyncio.get_running_loop()
    start = loop.time()
    await tool.get_account_state("CUST-2000")
    assert loop.time() - start >= 0.045


# --- raise_service_request -----------------------------------------------------------


def test_queue_catalogue_matches_pol_svc_006(settings: Settings) -> None:
    queues = load_queue_catalog(settings.corpus_dir, working_hours_per_day=8)
    assert {q: s.sla_hours for q, s in queues.items()} == {
        "CARDS_URGENT": 4,
        "DISPUTES": 16,
        "SELFSERVE": 8,
        "CREDIT_OPS": 24,
        "PAYMENTS": 16,
        "COMPLAINTS": 40,
        "GENERAL": 8,
    }


def test_unparseable_routing_policy_fails_loudly() -> None:
    with pytest.raises(ValueError):
        parse_queue_catalog("nothing useful here", working_hours_per_day=8)


async def test_raises_request_with_contract_shape(settings: Settings) -> None:
    tool = ServiceRequestTool(load_queue_catalog(settings.corpus_dir, 8))
    result = await tool.raise_service_request(
        "CUST-2002", "DISPUTES", "Unrecognised card-present txn"
    )
    assert set(result) == {"request_id", "queue", "sla_hours"}
    assert result["request_id"].startswith("SR-")
    assert (result["queue"], result["sla_hours"]) == ("DISPUTES", 16)
    assert len(tool.records()) == 1


@pytest.mark.parametrize("bad", ["disputes", "FRAUD", "Transaction dispute", ""])
async def test_never_guesses_a_category(settings: Settings, bad: str) -> None:
    tool = ServiceRequestTool(load_queue_catalog(settings.corpus_dir, 8))
    with pytest.raises(InvalidCategory):
        await tool.raise_service_request("CUST-2002", bad, "summary")
