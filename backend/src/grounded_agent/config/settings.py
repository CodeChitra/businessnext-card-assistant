"""Application settings.

Values come from environment variables, then `.env`, then `.env.local` (later files win,
real env vars beat both). `.env.local` is gitignored and holds developer-specific values.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/src/grounded_agent/config/settings.py -> repo root is four levels up.
REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", REPO_ROOT / ".env.local"),
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    data_dir: Path = REPO_ROOT / "data"
    cache_dir: Path = REPO_ROOT / "backend" / ".cache"

    # None means "today". Pinned in evals so time-dependent rules are reproducible.
    as_of_date: date | None = None

    # Simulated upstream behaviour for get_account_state (see data/tools.md).
    tool_latency_ms: int = Field(default=400, ge=0)
    tool_timeout_rate: float = Field(default=1 / 12, ge=0.0, le=1.0)
    tool_fault_seed: int | None = None

    # POL-SVC-006 states SLAs in working days; the tool contract returns hours.
    working_hours_per_day: int = Field(default=8, gt=0)

    # LangChain provider strings; credentials come from provider env vars.
    llm_primary_model: str = "openai:gpt-4o-mini"
    # Set to "none" to disable (e.g. a key that only grants one model).
    llm_fallback_model: str | None = "openai:gpt-4.1-mini"
    llm_judge_model: str = "openai:gpt-4.1-mini"  # evals only
    llm_temperature: float = 0.0
    llm_timeout_s: float = 60.0
    # Only sent to reasoning models (gpt-5*, o-series): minimal | low | medium | high.
    llm_reasoning_effort: str | None = None

    @field_validator("llm_fallback_model", "llm_reasoning_effort", mode="before")
    @classmethod
    def _none_means_unset(cls, v: object) -> object:
        return None if isinstance(v, str) and v.strip().lower() in {"", "none", "off"} else v

    # API
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    max_concurrent_turns: int = Field(default=16, gt=0)
    # Allows a request to force a tool timeout / primary-model outage for live demos.
    demo_faults: bool = False

    embedding_model: str = "BAAI/bge-small-en-v1.5"
    retrieval_top_k: int = Field(default=5, gt=0)
    rrf_k: int = Field(default=60, gt=0)
    # A query is a retrieval miss when no chunk clears either floor (tuned on the seed set).
    dense_min_score: float = 0.55
    bm25_min_score: float = 3.0

    @property
    def corpus_dir(self) -> Path:
        return self.data_dir / "policy_corpus"

    @property
    def accounts_path(self) -> Path:
        return self.data_dir / "accounts.json"

    def today(self) -> date:
        return self.as_of_date or date.today()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
