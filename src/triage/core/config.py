"""Application settings, loaded from the environment (prefix ``TRIAGE_``).

Every tunable lives here, never hard-coded at the call site. The set grows as
integrations land; defaults keep the deterministic core runnable with no env.
"""

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="TRIAGE_",
        extra="ignore",
        populate_by_name=True,  # allow field names too (alias used for env)
    )

    # --- auth ---
    api_key: str = "dev-key"

    # --- observability ---
    log_level: str = "INFO"  # set TRIAGE_LOG_LEVEL=DEBUG for the verbose per-node trace

    # --- llm / transcription (used from M11) ---
    # Accept the conventional unprefixed key names (what the SDKs use) as well as TRIAGE_-prefixed.
    openai_api_key: str = Field(
        default="", validation_alias=AliasChoices("TRIAGE_OPENAI_API_KEY", "OPENAI_API_KEY")
    )
    openai_model: str = "gpt-5.4-mini"
    deepgram_api_key: str = Field(
        default="", validation_alias=AliasChoices("TRIAGE_DEEPGRAM_API_KEY", "DEEPGRAM_API_KEY")
    )
    deepgram_model: str = "nova-3"
    llm_provider: str = "heuristic"  # "heuristic" (key-less) | "openai"
    transcriber: str = "fake"  # "fake" (key-less) | "deepgram"

    # --- infrastructure (used from M8/M9) ---
    persistence: str = "memory"  # "memory" | "postgres"
    execution: str = "inline"  # "inline" (graph in-request) | "queue" (arq worker)
    database_url: str = "postgresql://triage:triage@localhost:5432/triage"
    redis_url: str = "redis://localhost:6379/0"

    # --- input limits (cost / DoS guards on the paths into paid providers) ---
    max_message_chars: int = 4000
    max_voice_bytes: int = 25 * 1024 * 1024  # 25 MiB

    # --- operational (the async plane) ---
    lock_lease_seconds: int = 60  # per-conversation lease; heartbeat renews at a third of this
    idempotency_ttl_seconds: int = 24 * 60 * 60  # 24h replay window
    worker_max_tries: int = 3  # arq retries before dead-lettering

    # --- policy parameters (tunable, never hard-coded) ---
    clarification_cap: int = 2
    clarification_cap_sensitive: int = 1  # angry sentiment or critical urgency


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
