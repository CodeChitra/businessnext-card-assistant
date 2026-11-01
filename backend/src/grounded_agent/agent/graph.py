"""The agent as an explicit LangGraph state machine.

    input_guard   -> classify | short_circuit (another customer's data, or a pure greeting)
    classify      -> load_account | short_circuit (greeting, or out of scope: no human review)
    load_account  -> retrieve     | short_circuit (unknown customer)
    retrieve      -> policy       | uncovered (banking question the corpus cannot answer)
    policy        -> generate -> validate
    validate      -> act | repair (max 1, then validate again) | safe_fallback
    safe_fallback, uncovered -> act
    act, short_circuit -> finalize -> END

Safety-critical steps are fixed edges, not LLM choices: the model cannot skip the account
lookup, the rules engine or validation.
"""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from grounded_agent.agent.deps import AgentDeps
from grounded_agent.agent.nodes.generate import (
    GenerateNode,
    RepairNode,
    ValidateNode,
    route_after_validate,
)
from grounded_agent.agent.nodes.guard_and_account import InputGuardNode, LoadAccountNode
from grounded_agent.agent.nodes.respond import (
    ActNode,
    FinalizeNode,
    SafeFallbackNode,
    ShortCircuitNode,
    UncoveredNode,
    route_after_account,
    route_after_classify,
    route_after_guard,
    route_after_retrieve,
)
from grounded_agent.agent.nodes.understand import ClassifyNode, PolicyNode, RetrieveNode
from grounded_agent.agent.state import AgentState


def build_graph(deps: AgentDeps, checkpointer: BaseCheckpointSaver[Any] | None = None) -> Any:
    g = StateGraph(AgentState)
    g.add_node("input_guard", InputGuardNode())
    g.add_node("load_account", LoadAccountNode(deps))
    g.add_node("classify", ClassifyNode(deps))
    g.add_node("retrieve", RetrieveNode(deps))
    g.add_node("policy", PolicyNode(deps))
    g.add_node("generate", GenerateNode(deps))
    g.add_node("validate", ValidateNode(deps))
    g.add_node("repair", RepairNode(deps))
    g.add_node("safe_fallback", SafeFallbackNode())
    g.add_node("short_circuit", ShortCircuitNode())
    g.add_node("uncovered", UncoveredNode())
    g.add_node("act", ActNode(deps))
    g.add_node("finalize", FinalizeNode(deps))

    g.add_edge(START, "input_guard")
    g.add_conditional_edges("input_guard", route_after_guard, ["short_circuit", "classify"])
    g.add_conditional_edges("classify", route_after_classify, ["short_circuit", "load_account"])
    g.add_conditional_edges("load_account", route_after_account, ["short_circuit", "retrieve"])
    g.add_conditional_edges("retrieve", route_after_retrieve, ["uncovered", "policy"])
    g.add_edge("policy", "generate")
    g.add_edge("generate", "validate")
    g.add_conditional_edges("validate", route_after_validate, ["act", "repair", "safe_fallback"])
    g.add_edge("repair", "validate")
    g.add_edge("safe_fallback", "act")
    g.add_edge("uncovered", "act")
    g.add_edge("short_circuit", "finalize")
    g.add_edge("act", "finalize")
    g.add_edge("finalize", END)
    return g.compile(checkpointer=checkpointer)
