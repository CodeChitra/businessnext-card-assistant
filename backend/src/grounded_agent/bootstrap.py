"""Composition root: the only place concrete implementations are chosen and wired."""

from __future__ import annotations

from dataclasses import dataclass

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from grounded_agent.agent.deps import AgentDeps
from grounded_agent.agent.graph import build_graph
from grounded_agent.agent.service import AgentService
from grounded_agent.config.settings import Settings
from grounded_agent.llm.factory import build_chat_model
from grounded_agent.llm.structured import LangChainStructuredLLM, NamedModel, StructuredLLM
from grounded_agent.observability.env import load_environment
from grounded_agent.observability.metrics import PriceTable
from grounded_agent.observability.tracing import TracedRetriever, TracingStatus, configure_tracing
from grounded_agent.policy.fees import load_waiver_thresholds
from grounded_agent.policy.routing import load_queue_catalog
from grounded_agent.policy.rules import PolicyEngine
from grounded_agent.prompts.registry import PromptRegistry
from grounded_agent.repositories.base import AccountRepository
from grounded_agent.repositories.json_account_repository import JsonAccountRepository
from grounded_agent.retrieval.base import Embedder
from grounded_agent.retrieval.factory import build_retriever
from grounded_agent.tools.account_state import AccountStateTool
from grounded_agent.tools.faults import FaultInjector
from grounded_agent.tools.service_request import ServiceRequestTool

# Types that live in graph state and are read back from the checkpoint by `AgentService.snapshot`.
# LangGraph warns that unregistered types "will be blocked in a future version"; registering
# them keeps snapshots typed (not plain dicts) under strict msgpack. Nested models are rebuilt
# by their parents, so only the state's top-level types are listed.
CHECKPOINT_TYPES: tuple[tuple[str, str], ...] = (
    ("grounded_agent.domain.response", "AgentResponse"),
    ("grounded_agent.domain.response", "DraftResponse"),
    ("grounded_agent.domain.response", "IntentResult"),
    ("grounded_agent.domain.policy", "Trust"),
    ("grounded_agent.guardrails.input_guard", "InputFlags"),
    ("grounded_agent.llm.structured", "LLMCall"),
    ("grounded_agent.policy.rules", "PolicyAssessment"),
    ("grounded_agent.retrieval.base", "RetrievalResult"),
)


def build_llm(settings: Settings) -> StructuredLLM:
    names = [settings.llm_primary_model]
    if settings.llm_fallback_model and settings.llm_fallback_model != settings.llm_primary_model:
        names.append(settings.llm_fallback_model)
    return LangChainStructuredLLM(
        [
            NamedModel(
                name,
                build_chat_model(
                    name,
                    temperature=settings.llm_temperature,
                    timeout_s=settings.llm_timeout_s,
                    reasoning_effort=settings.llm_reasoning_effort,
                ),
            )
            for name in names
        ]
    )


@dataclass(frozen=True)
class Runtime:
    """What the API process holds: the agent plus read-only views the UI needs."""

    settings: Settings
    agent: AgentService
    deps: AgentDeps
    accounts: AccountRepository
    tracing: TracingStatus


def build_deps(
    settings: Settings,
    llm: StructuredLLM | None = None,
    embedder: Embedder | None = None,
    accounts: AccountRepository | None = None,
) -> AgentDeps:
    retriever = build_retriever(settings, embedder=embedder)
    queues = load_queue_catalog(settings.corpus_dir, settings.working_hours_per_day)
    return AgentDeps(
        account_tool=AccountStateTool(
            accounts or JsonAccountRepository(settings.accounts_path),
            FaultInjector(settings.tool_timeout_rate, seed=settings.tool_fault_seed),
            latency_ms=settings.tool_latency_ms,
        ),
        service_tool=ServiceRequestTool(queues),
        retriever=TracedRetriever(retriever),
        chunk_index=retriever,
        policy=PolicyEngine(load_waiver_thresholds(settings.corpus_dir)),
        llm=llm or build_llm(settings),
        prompts=PromptRegistry(),
        queues=queues,
        prices=PriceTable(),
        today=settings.today(),
    )


def build_runtime(
    settings: Settings,
    llm: StructuredLLM | None = None,
    embedder: Embedder | None = None,
    *,
    load_env: bool = True,
) -> Runtime:
    tracing = TracingStatus(False, None, "environment not loaded")
    if load_env:
        load_environment()
        tracing = configure_tracing()
    accounts = JsonAccountRepository(settings.accounts_path)
    deps = build_deps(settings, llm=llm, embedder=embedder, accounts=accounts)
    graph = build_graph(
        deps,
        checkpointer=InMemorySaver(
            serde=JsonPlusSerializer(allowed_msgpack_modules=CHECKPOINT_TYPES)
        ),
    )
    agent = AgentService(
        graph,
        today=deps.today,
        prompt_versions=deps.prompts.versions(),
        max_concurrent_turns=settings.max_concurrent_turns,
    )
    return Runtime(settings=settings, agent=agent, deps=deps, accounts=accounts, tracing=tracing)


def build_agent(
    settings: Settings,
    llm: StructuredLLM | None = None,
    embedder: Embedder | None = None,
    *,
    load_env: bool = True,
) -> AgentService:
    return build_runtime(settings, llm=llm, embedder=embedder, load_env=load_env).agent
