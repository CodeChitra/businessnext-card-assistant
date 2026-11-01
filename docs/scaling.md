# Scaling notes

**Status of the numbers.** Nothing here has been load-tested. Costs and latencies come from the 31-conversation application eval (`gpt-5`, reasoning effort low). Each section says whether something is **measured**, **built but unmeasured**, or **design only**.

## Cost per conversation (measured)

| | Per turn |
|---|---|
| Mean over all 31 eval turns | **$0.017** (p95 $0.032, max $0.049, the three-intent case) |
| A turn that calls the generator (26 of 31) | $0.020 on average: 3,750 tokens in, 1,530 out |
| A blocked or greeting turn | $0.00 to $0.0013 |

Output tokens are priced eight times input (`gpt-5`: $1.25 and $10 per million), and a reasoning model spends many of them thinking, so **the generation call is the cost**. Everything the system does itself (retrieval, rules, validation, guards) is CPU and costs nothing per token. At today's mix, a million turns a month is roughly $17,000.

Levers, in the order I would pull them:

1. **Not calling the model.** Built: the scope gate answers greetings and off-topic questions with one small classifier call or none (AP-016: $0.0013; a greeting: $0).
2. A **cheaper model for the classifier** (it needs 770 tokens in and 30 out). Design only.
3. **Less reasoning, or a non-reasoning model, for simple lookups.** The fee lookup AP-001 cost $0.0096 against $0.049 for a three-intent question, so a router on intent would pay for itself. Design only.
4. **Smaller prompts.** Chunks are coarse (the fee schedule is one chunk of seven rows), so every fee question sends all seven rows. Row-level chunking would cut input tokens and fix contextual relevancy (0.35) at once. Design only.
5. **A response cache for non-personal FAQ answers**, keyed by tenant and intent, never for account-dependent answers. Design only.

## Latency (measured)

p50 18.5 s, p95 33.9 s. The live traces in [`sample_traces.md`](sample_traces.md) show where it goes: `generate` takes 5.8 s of a 9.9 s turn, 16.5 s of 19.2 s, 14.3 s of 17.4 s; classify takes 2 to 3 s; the account tool 0.4 s; retrieval, rules and validation under 0.1 s. Cutting latency means cutting the generator's work (lever 3 above), not optimising our code. The UI hides the wait with a live step label and, once the answer arrives, a progressive reveal.

## Caching

| | Status |
|---|---|
| Embeddings and index persisted by corpus fingerprint, rebuilt only when the corpus or embedding model changes | built |
| Retrieval results cached by normalised query (LRU, 256 entries) | built, hit rate unmeasured |
| **Account state is never cached**: stale balances are a correctness and compliance risk | by design |
| Stable system prompt first, so provider prompt caching can apply | structure only; the policy context varies per turn, so the cacheable prefix is small. Unmeasured |
| Semantic or response cache | not built |

## Streaming

The server streams one `progress` event per graph step and then the **validated** reply; the client reveals that reply progressively. Raw model tokens are never shown, because citations and numbers are validated on the complete draft and a repair pass may rewrite it: showing tokens early would show claims that may be rejected. The cost is time-to-first-text. The way to recover it is an **incremental validator** that checks each claim as the structured output streams in; that is a real piece of work and is not built.

## Concurrency

Built: async FastAPI, async tool calls, and a semaphore that bounds concurrent turns (16 by default) and so concurrent model calls per process. The model client retries once (`max_retries=1`, 60 s timeout) and there is no queue or limiter in front of it, so a sustained `429` from the provider would surface as a model outage and fall through to the static last resort. **Not load-tested.**

What stops it scaling out today: conversation state lives in an **in-memory checkpointer**, so a thread is tied to one process and lost on restart. To run replicas, move the checkpointer to Redis or Postgres so any replica can resume any thread, and add a per-tenant rate limiter and queue in front of the model so one tenant's burst cannot starve another or trip the provider's limit.

## A corpus 100 times larger, split across customer tenancies (design only)

**What breaks first**

- **Isolation.** Today there is one corpus and one index. With tenants, a retrieval that is not tenant-scoped is a data breach. The tenant must come from the authenticated session (already true of the customer id: a conversation thread that belongs to another customer is never continued or forked, with a test), and retrieval must **filter by tenant and ACL before scoring, never after**.
- **Hand-written knowledge.** The precedence table (`policy/precedence.py`), the rules engine and the waiver thresholds are derived from this corpus by hand. At 100x they must become data: contradictions detected at **ingestion**, not remembered by a person; rules owned per tenant and versioned.
- **Calibration.** The relevance floors that decide "retrieval miss" were tuned on 28 questions. Each tenant needs its own, measured on its own goldens.
- **Trust.** The corpus contains a document that is not policy (POL-OPS-012) and carries an injected instruction. At scale, trust classification, effective dates and versions are an ingestion step with review, not a filename convention.

**Shape of the design**

1. **Index:** a vector store with per-tenant collections or a mandatory `tenant_id` filter (Qdrant or pgvector), plus BM25 in a search engine (OpenSearch), fused with the same reciprocal-rank fusion as now; a cross-encoder reranker after it.
2. **Ingestion pipeline:** parse, structure-aware chunking (table rows, not whole tables), trust classification, version and effective-date metadata, contradiction detection, human review before publish. Embeddings versioned by fingerprint so a re-embed is a rollout, not an outage.
3. **No cross-tenant caches:** every cache key includes the tenant.
4. **Evaluation per tenant:** the harness already takes goldens as data (`evals/datasets/*.yaml`) and has a deterministic gate; each tenant gets its own sets, thresholds and prompt versions, and a sample of live conversations is evaluated against the same metrics.
5. **Audit:** every response already carries prompt versions, model, rules fired and citations; at scale these go to an immutable store keyed by tenant and thread.

**What I would measure before building any of it:** throughput against p95 and `429` rate at rising concurrency; cost per *resolved* conversation (not per turn); cache hit rates; and per-tenant miss-floor calibration.
