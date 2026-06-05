"""Runtime configuration, loaded from environment variables / a local .env file."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration object.

    Values are read from environment variables (prefixed ``DPA_`` where noted) or a
    ``.env`` file in the project root. Every field has a safe default so the app runs
    out of the box, even with no API key.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- AI backend -------------------------------------------------------
    anthropic_api_key: str = ""
    dpa_model: str = "claude-opus-4-8"

    # Free alternative: Google Gemini (https://aistudio.google.com — no card needed).
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # "auto" -> Claude if its key is set, else Gemini if its key is set, else heuristic.
    # Can also be forced to "claude", "gemini" or "heuristic".
    dpa_engine: str = "auto"
    dpa_max_text_chars: int = 18_000
    dpa_use_vision: bool = True

    # --- Fetching ---------------------------------------------------------
    dpa_fetch_timeout: int = 30

    # --- Web server -------------------------------------------------------
    dpa_host: str = "127.0.0.1"
    dpa_port: int = 8000

    @property
    def has_api_key(self) -> bool:
        return bool(self.anthropic_api_key and self.anthropic_api_key.strip())

    @property
    def has_gemini_key(self) -> bool:
        return bool(self.gemini_api_key and self.gemini_api_key.strip())

    def resolved_engine(self) -> str:
        """Return the concrete engine to use: ``claude``, ``gemini`` or ``heuristic``."""
        choice = (self.dpa_engine or "auto").lower()
        if choice in {"claude", "gemini", "heuristic"}:
            return choice
        # auto: prefer Claude, then Gemini, then the offline heuristic engine.
        if self.has_api_key:
            return "claude"
        if self.has_gemini_key:
            return "gemini"
        return "heuristic"

    def active_model(self) -> str | None:
        """The model name for the resolved engine (None for the heuristic engine)."""
        engine = self.resolved_engine()
        if engine == "claude":
            return self.dpa_model
        if engine == "gemini":
            return self.gemini_model
        return None


settings = Settings()
