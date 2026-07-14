"""
core/config.py — Centralized, validated configuration management.

Pattern: Singleton Settings via pydantic-settings BaseSettings.
Security: Secrets are NEVER hardcoded. Process fails loudly at startup
          if required env vars are missing (fail-secure posture).
Future:   Add fields here for OPENAI_API_KEY, REDIS_URL, etc.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application-wide settings loaded from environment / .env file.

    All fields are validated at process startup via Pydantic.
    If a required field is missing, the process crashes with a
    clear ValidationError — no silent failures, ever.
    """

    model_config = SettingsConfigDict(
        # Resolve .env relative to THIS file's directory (project-pulse/.env)
        env_file=Path(__file__).parents[2] / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",          # silently ignore unknown env vars (safe)
    )

    # ── Supabase ──────────────────────────────────────────────────────────────
    supabase_url: AnyHttpUrl = Field(
        ...,
        description="Your Supabase project URL (e.g. https://<ref>.supabase.co)",
    )
    supabase_key: SecretStr = Field(
        ...,
        description="Supabase anon/service_role key. Never log this value.",
    )

    # ── Application Meta ──────────────────────────────────────────────────────
    app_name: str = Field(default="Project Pulse", description="Application display name.")
    app_env: str = Field(default="development", description="Environment: development | staging | production.")
    log_level: str = Field(default="INFO", description="Logging level: DEBUG | INFO | WARNING | ERROR.")

    # ── Future: AI / Vector Store ─────────────────────────────────────────────
    # openai_api_key: SecretStr | None = Field(default=None)
    # google_api_key: SecretStr | None = Field(default=None)
    # redis_url: AnyUrl | None = Field(default=None)

    @field_validator("app_env")
    @classmethod
    def validate_env(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        if v.lower() not in allowed:
            raise ValueError(f"app_env must be one of {allowed}, got '{v}'")
        return v.lower()

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return upper

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def supabase_url_str(self) -> str:
        """Return Supabase URL as plain string (Supabase SDK requires str, not AnyHttpUrl)."""
        return str(self.supabase_url)

    @property
    def supabase_key_str(self) -> str:
        """Return Supabase key as plain string — ONLY call inside the DB client factory."""
        return self.supabase_key.get_secret_value()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Singleton accessor for Settings.

    lru_cache(maxsize=1) ensures Settings is instantiated exactly once
    per process lifetime — O(1) subsequent lookups with zero I/O.
    Use `get_settings.cache_clear()` in tests to reset state.
    """
    return Settings()
