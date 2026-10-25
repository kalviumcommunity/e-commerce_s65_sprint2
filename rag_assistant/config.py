from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigurationError(ValueError):
    """Raised when required runtime configuration is missing or invalid."""


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be a number") from exc
    if value < 0:
        raise ConfigurationError(f"{name} must be non-negative")
    return value


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ConfigurationError(f"{name} must be greater than zero")
    return value


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str
    model: str
    timeout_seconds: float = 30.0
    input_cost_per_1k: float = 0.0
    output_cost_per_1k: float = 0.0
    context_window: int = 8192

    @classmethod
    def from_env(cls, *, require_api_key: bool = True) -> "Settings":
        api_key = os.getenv("LLM_API_KEY", "").strip()
        if require_api_key and (not api_key or api_key == "replace-me"):
            raise ConfigurationError("LLM_API_KEY is missing; set it in the environment")
        base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        model = os.getenv("LLM_MODEL", "").strip()
        if not model:
            raise ConfigurationError("LLM_MODEL is missing; set the provider model name")
        timeout = _float("LLM_TIMEOUT_SECONDS", 30.0)
        if timeout <= 0:
            raise ConfigurationError("LLM_TIMEOUT_SECONDS must be greater than zero")
        return cls(api_key, base_url, model, timeout, _float("LLM_INPUT_COST_PER_1K", 0),
                   _float("LLM_OUTPUT_COST_PER_1K", 0), _int("LLM_CONTEXT_WINDOW", 8192))

