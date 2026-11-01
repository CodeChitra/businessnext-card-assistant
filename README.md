# Grounded card service agent

Answers a bank cardholder's questions about **their card** from the supplied policy corpus and their own account only. Every claim carries a citation the system checks; when the corpus cannot answer, it says so and routes to a person. FastAPI + LangGraph, React UI. Design: [`SPEC.md`](SPEC.md) · evals: [`evals/README.md`](evals/README.md) · real transcripts: [`docs/sample_traces.md`](docs/sample_traces.md), [`docs/failure_modes.md`](docs/failure_modes.md) · workflow diagram and trade-offs: [`docs/architecture.md`](docs/architecture.md) · scale: [`docs/scaling.md`](docs/scaling.md).

## Setup and run

Works the same on Windows, macOS and Linux. The commands below are plain `uv` and `npm` calls, so `make` is **not** required (it is only a shortcut; see the last note).

### Prerequisites

| Tool                                                          | Version      | Install                                                                                      |
| ------------------------------------------------------------- | ------------ | -------------------------------------------------------------------------------------------- |
| Python                                                        | 3.11 to 3.13 | [python.org](https://www.python.org/downloads/) (`uv` can also fetch it for you)             |
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | recent       | Windows: `winget install astral-sh.uv` · macOS: `brew install uv` · any OS: `pip install uv` |
| Node.js + npm                                                 | 22           | [nodejs.org](https://nodejs.org/)                                                            |
| An OpenAI-compatible API key                                  | n/a          | needed for live answers and evals; unit tests need none                                      |

### 1. Install dependencies

One command, from the repository root, in any shell (PowerShell, cmd, bash, zsh). It checks that `uv`, Node and npm are present, installs the backend and frontend, and creates `.env.local` from the template if it does not exist (it never overwrites one):

```
python scripts/setup.py        # on Windows, `py scripts/setup.py` also works
```

Then jump to step 2 to fill in `.env.local`. To do it by hand instead:

```
cd backend
uv sync --all-groups
cd ../frontend
npm ci
cd ..
```

### 2. Configure

Create `.env.local` in the repository root from the template. It is gitignored. Use whichever line matches your shell:

```
# macOS / Linux / Git Bash
cp .env.example .env.local

# Windows PowerShell
Copy-Item .env.example .env.local

# Windows cmd
copy .env.example .env.local
```

Then edit `.env.local` and set at least `OPENAI_API_KEY` and the `LLM_*_MODEL` values. Optional lines:

- `OPENAI_BASE_URL`: use an OpenAI-compatible gateway.
- `DEMO_FAULTS=true`: enables the `simulate=timeout|primary_down` failure demos.
- `LANGSMITH_TRACING=false`: turn tracing off if you have no LangSmith key.

Put settings in this file rather than in shell variables: it behaves identically on every OS.

### 3. Run (two terminals, both from the repository root)

```
# Terminal 1: API on http://localhost:8000
cd backend
uv run uvicorn grounded_agent.api.app:app --reload --port 8000

# Terminal 2: UI on http://localhost:5173 (proxies /api to :8000)
cd frontend
npm run dev
```

Open <http://localhost:5173>. Check the API with <http://localhost:8000/health>, which should return `"status":"ok"`.
If port 8000 is taken, pick another and tell the UI where it is: start uvicorn with `--port 8001`, and in terminal 2 set `VITE_API_TARGET=http://127.0.0.1:8001` first (`export VITE_API_TARGET=...` on macOS/Linux, `$env:VITE_API_TARGET="..."` in PowerShell, `set VITE_API_TARGET=...` in cmd).

The first request downloads the small embedding model (`BAAI/bge-small-en-v1.5`), so it needs internet once and is slower than later ones.

### 4. Test and evaluate

```
cd backend && uv run pytest -q        # unit and integration tests, no keys, no network
cd frontend && npm test               # UI tests
cd backend && uv run ruff check src tests && uv run mypy src   # lint and types
```

Evals need the repository root as working directory:

```
uv run --project backend python -m evals.component.retrieval.run --no-llm   # deterministic, no keys
```

Other layers (generation, pipeline, application) need live models; see [`evals/README.md`](evals/README.md).

### Troubleshooting

- **`Address already in use`**: another process holds port 8000 or 5173. Stop it or use another port as above.
- **Answers fail with an auth error**: `OPENAI_API_KEY` is missing or empty in `.env.local`.
- **Behind a corporate proxy or custom CA**: set `SSL_CERT_FILE` in `.env.local`.
- **`uv` not found after install (Windows)**: open a new terminal so `PATH` refreshes.
- **Optional `make` shortcuts** (macOS/Linux, or Windows with `make` installed): `make setup`, `make api`, `make web`, `make check`, `make eval`. They run the same commands as above. `make check` also runs `scripts/hygiene.sh`, which needs bash (Git Bash or WSL on Windows).

## 1. What I built

A LangGraph state machine where safety-critical steps are fixed edges, not model choices. A **scope gate** answers greetings and unrelated questions at once. **Hybrid retrieval** (BM25 + embeddings, rank fusion, relevance floors) feeds a **deterministic rules engine** that, not the model, decides every credit outcome. The generator's structured output passes a **citation validator** (each claim needs a trusted chunk, an account field fetched this turn, or a rule; every number must appear in its source), then one repair, then a safe fallback. The supplied tools follow their contracts, and their timeout becomes a designed **degraded mode**. The UI streams progress, renders cited Markdown answers, suggests next questions, and supports edit and replay. A four-layer DeepEval suite runs 31 goldens (12 supplied, 19 mine).

| Layer (committed reports, `gpt-5`) | Result                                                                                                      |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| Retrieval (28)                     | recall@k 1.00, reciprocal rank 0.94                                                                         |
| Generation (15) / Pipeline (15)    | faithfulness 0.99, answer relevancy 0.95; contextual relevancy **0.35**                                     |
| Application (31)                   | safety 100%, correctness 0.94, completeness 0.88; **24/31 pass**; p50 18.5 s; about $0.017 per conversation |

**The application gate currently fails**: one critical case (AP-008) acts correctly but is labelled `answer`, not `refuse`. Reports are committed as they came out.

## 2. What I deliberately did not build

- **Vector DB, reranker, Graph RAG:** 12 documents; they would add setup and cost auditability.
- **Real auth, persistent conversation store:** the session `customer_id` stands in; history is in memory.
- **Raw token streaming:** citations are validated on the complete draft, so tokens would show claims that may be rejected. The server streams progress, then the _validated_ reply.
- **Account snapshot, transactions, request tracking:** no data or endpoint exists; I would not invent them.
- **100x multi-tenant corpus, Docker, a review-queue UI:** designed, not built ([`docs/scaling.md`](docs/scaling.md)).

## 3. What I would do next

1. Known and left as is: AP-008 labels a correct refusal `answer` (the one failing gate); general requests show an internal phrase ("cannot be categorised with confidence") in the raw API message; EV-003's decline gives no reason now and defers it ("within 7 days"). That last one is a **policy gap, not a clear bug**: POL-CRD-001 §4 says so, and no approved reason code (AA01 to AA06) fits a conduct decline, so it needs a decision from the Conduct team.
2. **Row-level chunking of tables** (the fee schedule is one chunk, hence contextual relevancy 0.35).
3. Working tracing, a persistent checkpointer, a judge from a different model family, many more adversarial goldens.

## 4. What I would not trust, and how to find out

- **The eval numbers.** Same-family judge, 31 coarse cases, my own reference answers, and **I changed the suite after the first run** (listed in `evals/README.md`). _Check:_ `make eval-application ARGS="--reuse-runs"`; swap `LLM_JUDGE_MODEL`; read the replies in the reports.
- **My predictions.** I predicted three failures and **all three passed**; the real failures were ones I missed. _Check:_ try multi-turn, mixed-language and long messages.
- **The scope gate.** A wrong "out of scope" silently blocks a real question; only four goldens test the boundary. _Check:_ "my cousin asks about credit cards", "tell me a joke about banks".
- **Safety rules are patterns**, not understanding. _Check:_ ask cardholder Saanvi Malhotra for offers and read the wording.
- **Tracing is unverified.** LangSmith uploads returned `403` with my key; tokens, cost and latency are in every response's `meta`.
- **Fallback and concurrency are not exercised live:** no second model is configured here, and nothing is load-tested. _Check:_ set `LLM_FALLBACK_MODEL`, use `simulate=primary_down`.
- **State is in memory.** Restart mid-conversation, then edit an old message: it answers without its context.
- **CI is written, not yet run on GitHub.** The backend job runs a keyless retrieval gate; the live application gate reports _skipped_ without keys and will fail until AP-008 is fixed.
- **My reading of the corpus:** the 8-hour working day behind each SLA, and "income unknown means refer" (SPEC §5.3, §16).

Built with Claude Code assistance; `SPEC.md` and `CLAUDE.md` record the decisions and working rules.
