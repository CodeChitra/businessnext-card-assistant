"""HTTP API.

    uvicorn grounded_agent.api.app:app --reload

`create_app()` takes an optional prebuilt Runtime so tests (and offline demos) can inject
a scripted LLM; production builds everything from Settings in the lifespan.

Customer-visible failure is designed, not accidental: tool timeouts and model outages are
handled inside the agent and arrive as normal responses (degraded / safe fallback). The
only HTTP errors are client mistakes (4xx) and genuinely unexpected faults, which return a
generic message, never a stack trace.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterable, AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Body, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.sse import EventSourceResponse, ServerSentEvent

from grounded_agent.api.schemas import (
    ChatRequest,
    CustomerSummary,
    ErrorView,
    HealthView,
    PolicyChunkView,
)
from grounded_agent.bootstrap import Runtime, build_runtime
from grounded_agent.config.settings import Settings, get_settings
from grounded_agent.domain.response import AgentResponse

log = logging.getLogger(__name__)
UNEXPECTED = "Something went wrong on our side. Please try again in a moment."


def runtime(request: Request) -> Runtime:
    rt: Runtime = request.app.state.runtime
    return rt


def chat_body(body: Annotated[ChatRequest, Body()], request: Request) -> ChatRequest:
    # A dependency, so it runs before a streaming response has sent its headers.
    if body.simulate and not runtime(request).settings.demo_faults:
        raise HTTPException(400, "simulate is only available when DEMO_FAULTS=true")
    if body.rewind_to is not None and not body.thread_id:
        raise HTTPException(400, "rewind_to needs a thread_id")
    return body


def create_app(
    settings: Settings | None = None, runtime_factory: Callable[[], Runtime] | None = None
) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.runtime = runtime_factory() if runtime_factory else build_runtime(settings)
        yield

    app = FastAPI(
        title="Grounded Card Service Agent",
        version="0.1.0",
        description="Grounded, cited answers about a customer's card, with designed refusal.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.exception_handler(Exception)
    async def unexpected(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error", exc_info=exc)
        return JSONResponse(ErrorView(error=UNEXPECTED).model_dump(), status_code=500)

    @app.post("/api/chat", response_model=AgentResponse, responses={400: {"model": ErrorView}})
    async def chat(
        request: Request, body: Annotated[ChatRequest, Depends(chat_body)]
    ) -> AgentResponse:
        rt = runtime(request)
        return await rt.agent.run(
            body.customer_id, body.message, body.thread_id, body.simulate, body.rewind_to
        )

    @app.post("/api/chat/stream", response_class=EventSourceResponse)
    async def chat_stream(
        request: Request, body: Annotated[ChatRequest, Depends(chat_body)]
    ) -> AsyncIterable[ServerSentEvent]:
        """SSE: `progress` events per step, then one `final` (validated AgentResponse)."""
        rt = runtime(request)
        try:
            async for event in rt.agent.stream(
                body.customer_id, body.message, body.thread_id, body.simulate, body.rewind_to
            ):
                yield ServerSentEvent(data=event.data, event=event.type)
        except Exception:  # headers are already sent; report in-band
            log.exception("stream failed")
            yield ServerSentEvent(data=ErrorView(error=UNEXPECTED).model_dump(), event="error")

    @app.get("/api/customers", response_model=list[CustomerSummary])
    async def customers(request: Request) -> list[CustomerSummary]:
        """Demo customer picker (stands in for an authenticated session)."""
        accounts = runtime(request).accounts
        out = []
        for cid in accounts.list_ids():
            acct = accounts.get(cid)
            if acct is not None:
                out.append(
                    CustomerSummary(customer_id=cid, name=acct.name, card_product=acct.card_product)
                )
        return out

    @app.get(
        "/api/policies/{doc_id}/{section}",
        response_model=PolicyChunkView,
        responses={404: {"model": ErrorView}},
    )
    async def policy_chunk(doc_id: str, section: str, request: Request) -> PolicyChunkView:
        """Source text behind a citation chip, e.g. /api/policies/POL-FEE-007/body."""
        chunk = runtime(request).deps.chunk_index.get_chunk(f"{doc_id}#{section}")
        if chunk is None:
            raise HTTPException(404, f"No policy chunk {doc_id}#{section}")
        return PolicyChunkView(
            chunk_id=chunk.chunk_id,
            doc_id=chunk.doc_id,
            title=chunk.title,
            heading=chunk.heading,
            section=chunk.section,
            version=chunk.version,
            effective_date=chunk.effective_date,
            trust=chunk.trust.value,
            text=chunk.text,
        )

    @app.get("/health", response_model=HealthView)
    async def health(request: Request) -> HealthView:
        rt = runtime(request)
        s = rt.settings
        tracing: dict[str, Any] = {
            "enabled": rt.tracing.enabled,
            "project": rt.tracing.project,
            "reason": rt.tracing.reason,
        }
        return HealthView(
            status="ok",
            as_of_date=rt.deps.today.isoformat(),
            chunks_indexed=len(rt.deps.chunk_index.chunks),
            models={
                "primary": s.llm_primary_model,
                "fallback": s.llm_fallback_model,
                "embedding": s.embedding_model,
            },
            prompt_versions=rt.deps.prompts.versions(),
            tracing=tracing,
            demo_faults=s.demo_faults,
        )

    return app


app = create_app()
