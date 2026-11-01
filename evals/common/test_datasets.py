"""The goldens are test data, so they get tests: counts, references and cross-file sync."""

from __future__ import annotations

import csv
import json

import pytest

from evals.common.datasets import (
    ApplicationGolden,
    load_application_goldens,
    load_generation_goldens,
    load_pipeline_goldens,
    select,
)
from grounded_agent.config.settings import REPO_ROOT, get_settings
from grounded_agent.policy.routing import load_queue_catalog
from grounded_agent.retrieval.chunker import chunk_corpus
from grounded_agent.retrieval.loader import load_corpus

APP = load_application_goldens()
GEN = load_generation_goldens()
PIPE = load_pipeline_goldens()
ACCOUNTS = json.loads((REPO_ROOT / "data" / "accounts.json").read_text())
SEED = list(csv.DictReader((REPO_ROOT / "data" / "eval_seed.csv").open()))


def test_sizes_match_the_brief_and_the_demo_plan() -> None:
    assert len(GEN) == 15 and len(PIPE) == 15
    assert len([g for g in APP if g.id.startswith("EV-")]) == 12  # the supplied seed
    assert len([g for g in APP if g.id.startswith("AP-")]) >= 15  # "at least fifteen of your own"
    assert len({g.id for g in APP}) == len(APP)


def test_seed_cases_are_the_supplied_ones() -> None:
    by_id = {g.id: g for g in APP}
    for row in SEED:
        g = by_id[row["case_id"]]
        assert (g.customer_id, g.question) == (row["customer_id"], row["question"])
        assert g.expected_behaviour == row["expected_behaviour"]


def test_demo_set_is_exactly_the_generation_and_pipeline_set() -> None:
    demo = {g.id for g in APP if "demo" in g.tags}
    assert demo == {g.id for g in GEN} == {g.id for g in PIPE}


@pytest.mark.parametrize("layer", [GEN, PIPE], ids=["generation", "pipeline"])
def test_layer_goldens_copy_the_master_exactly(layer: list) -> None:  # type: ignore[type-arg]
    master = {g.id: g for g in APP}
    for g in layer:
        m = master[g.id]
        assert (g.customer_id, g.question, g.expected_output) == (
            m.customer_id,
            m.question,
            " ".join(m.expected_output.split()),
        ), f"{g.id} drifted from application_goldens.yaml; regenerate it"


def test_gold_chunks_exist_in_the_corpus() -> None:
    chunk_ids = {c.chunk_id for c in chunk_corpus(load_corpus(get_settings().corpus_dir))}
    for g in GEN:
        assert set(g.gold_chunks) <= chunk_ids, g.id


def test_customers_and_queues_are_real() -> None:
    queues = load_queue_catalog(get_settings().corpus_dir, 8)
    for g in APP:
        assert g.customer_id in ACCOUNTS, g.id
        assert g.expected_queue is None or g.expected_queue in queues, g.id


def test_expected_failures_are_predicted_with_a_reason() -> None:
    xfail = [g for g in APP if g.expected_fail]
    assert 2 <= len(xfail) <= 4  # "cases you expect to fail", a few, not a way to dodge the rate
    assert all((g.expected_fail_reason or "").strip() for g in xfail)
    assert not any(g.critical for g in xfail)


def test_expected_fail_without_a_reason_is_rejected() -> None:
    with pytest.raises(ValueError, match="expected_fail needs"):
        ApplicationGolden(
            id="X",
            customer_id="CUST-2000",
            question="q",
            expected_output="a",
            expected_behaviour="answer",
            expected_fail=True,
        )


def test_the_timeout_case_forces_the_fault_and_forbids_account_figures() -> None:
    ap15 = next(g for g in APP if g.id == "AP-015")
    assert ap15.simulate == "timeout"
    assert "1,62,000" in ap15.must_not_mention  # CUST-2000's card_year_spend


def test_select_filters_and_rejects_typos() -> None:
    assert [g.id for g in select(APP, ids="EV-001,AP-001")] == ["EV-001", "AP-001"]
    assert len(select(APP, tag="demo")) == 15
    with pytest.raises(ValueError, match="unknown golden ids"):
        select(APP, ids="EV-999")
    with pytest.raises(ValueError, match="matched no goldens"):
        select(APP, tag="nonexistent")


def test_scope_cases_assert_that_no_human_review_is_raised() -> None:
    scope = [g for g in APP if "scope" in g.tags]
    assert {g.id for g in scope} >= {"AP-016", "AP-017", "AP-018", "AP-019"}
    out_of_scope = [g for g in scope if g.no_request]
    assert out_of_scope and all(g.expected_queue is None for g in out_of_scope)
    # ...whereas a banking question the corpus cannot answer must reach a person.
    assert next(g for g in APP if g.id == "AP-019").expected_queue == "GENERAL"


def test_a_case_cannot_both_forbid_and_require_a_request() -> None:
    assert not [g for g in APP if g.no_request and g.expected_queue]
