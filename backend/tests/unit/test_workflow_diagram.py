"""The workflow picture is generated from the compiled graph and must never drift from it."""

from __future__ import annotations

import importlib.util
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from grounded_agent.bootstrap import build_runtime
from grounded_agent.config.settings import REPO_ROOT, Settings
from grounded_agent.llm.fake import FakeStructuredLLM

SCRIPT = REPO_ROOT / "scripts" / "workflow_diagram.py"
SVG = REPO_ROOT / "docs" / "workflow.svg"


@pytest.fixture(scope="module")
def diagram():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("workflow_diagram", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def real_edges(diagram, settings: Settings, hashing_embedder):  # type: ignore[no-untyped-def]
    rt = build_runtime(settings, llm=FakeStructuredLLM(), embedder=hashing_embedder, load_env=False)
    return diagram.graph_edges_of(rt.agent._graph)


def test_the_drawing_covers_exactly_the_edges_of_the_real_graph(diagram, real_edges) -> None:  # type: ignore[no-untyped-def]
    assert set(diagram._edges()) == real_edges


def test_a_graph_change_that_is_not_drawn_is_an_error(diagram, real_edges) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError, match="In the graph but not drawn"):
        diagram.render(real_edges | {("classify", "act")})
    with pytest.raises(ValueError, match="drawn but not in the graph"):
        diagram.render(real_edges - {("act", "finalize")})


def test_the_committed_svg_is_not_stale(diagram, real_edges) -> None:  # type: ignore[no-untyped-def]
    assert SVG.read_text() == diagram.render(real_edges), (
        "docs/workflow.svg is stale: run `make workflow` and commit it"
    )


def test_the_svg_is_valid_and_names_every_step(diagram, real_edges) -> None:  # type: ignore[no-untyped-def]
    root = ET.fromstring(diagram.render(real_edges))
    text = " ".join("".join(el.itertext()) for el in root.iter() if el.tag.endswith("text"))
    for node in {n for e in real_edges for n in e} - {"__start__", "__end__"}:
        assert node in text, f"{node} is missing from the picture"
    assert Path(SVG).exists()
