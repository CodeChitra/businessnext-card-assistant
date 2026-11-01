"""Hand-built runs for tests: no agent, no network."""

from __future__ import annotations

from evals.common.agent_runs import AgentRun, Grounding, RetrievedView
from grounded_agent.domain.response import AgentResponse, ResponseMeta


def fake_run(id: str = "EV-009", message: str = "The foreign currency markup is 3.5%.") -> AgentRun:
    return AgentRun(
        id=id,
        customer_id="CUST-2007",
        question="What is the markup in Singapore?",
        response=AgentResponse(
            behaviour="answer",
            message=message,
            meta=ResponseMeta(model="m", latency_ms=1000),
        ),
        grounding=Grounding(
            retrieved=[
                RetrievedView(
                    chunk_id="POL-FEE-007#body",
                    trust="policy",
                    title="Fees and Charges Schedule",
                    text="Foreign currency markup | 3.5%",
                    via="search",
                ),
                RetrievedView(
                    chunk_id="POL-OPS-012#body",
                    trust="non_policy",
                    title="Agent Desktop Notes",
                    text="informal notes",
                    via="search",
                ),
            ],
            policy_context=["[POL-FEE-007#body] Foreign currency markup | 3.5%"],
            account_facts="- account.customer_id: CUST-2007",
            rule_outcomes="DECISION: none",
            precedence_notes="(none)",
            miss=False,
            intent="fee",
        ),
    )
