.PHONY: setup api web test test-web lint typecheck check eval eval-retrieval eval-retrieval-llm eval-generation eval-pipeline eval-application eval-demo hygiene workflow

UV := uv run --project backend

setup:            ## install backend (incl. eval group) and frontend deps
	cd backend && uv sync --all-groups
	cd frontend && npm ci

api:              ## run the API on :8000 (DEMO_FAULTS=true enables simulate=timeout|primary_down)
	cd backend && uv run uvicorn grounded_agent.api.app:app --reload --port 8000

web:              ## run the UI on :5173 (proxies /api to :8000)
	cd frontend && npm run dev

test:             ## unit + integration tests (no network, scripted LLM)
	cd backend && uv run pytest -q
	$(UV) pytest evals -q

test-web:
	cd frontend && npm test

lint:
	$(UV) ruff check backend/src backend/tests evals
	$(UV) ruff format --check backend/src backend/tests evals
	cd frontend && npm run lint

typecheck:
	cd backend && uv run mypy src
	cd frontend && npx tsc -b --noEmit

hygiene:          ## no private hosts, keys or local files in tracked files
	scripts/hygiene.sh

workflow:         ## regenerate docs/workflow.svg from the compiled graph
	PYTHONPATH=backend/src $(UV) python scripts/workflow_diagram.py

check: lint typecheck test test-web hygiene   ## everything CI runs without API keys

eval-retrieval:   ## retrieval component eval, deterministic metrics only
	$(UV) python -m evals.component.retrieval.run --no-llm

eval-retrieval-llm: ## + LLM-judged contextual metrics (needs a judge model; slow on reasoning models)
	$(UV) python -m evals.component.retrieval.run --max-concurrent 2 --throttle 2

# The three layers below call the live models configured in .env.local (agent + judge). Pass
# options through ARGS, e.g.  make eval-pipeline ARGS="--ids EV-001,EV-004 --no-llm"
eval-generation:  ## generator only, retrieval pinned to gold chunks: Faithfulness, Answer Relevancy
	$(UV) python -m evals.component.generation.run $(ARGS)

eval-pipeline:    ## RAG triad on live retrieval + generation: Contextual Relevancy, Faithfulness, Answer Relevancy
	$(UV) python -m evals.pipeline.rag_triad.run $(ARGS)

eval-application: ## full agent: Latency, Cost, Completeness, Correctness, PII and Safety (--gate fails CI on a hard gate)
	$(UV) python -m evals.application.run $(ARGS)

eval-demo:        ## the 15 demo goldens through all three layers
	$(MAKE) eval-generation eval-pipeline
	$(MAKE) eval-application ARGS="--tag demo"

eval: eval-retrieval eval-generation eval-pipeline eval-application  ## every layer, full goldens
