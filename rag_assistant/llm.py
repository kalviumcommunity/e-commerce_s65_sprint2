from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from .config import Settings
from .tokens import TokenCounter, UsageEstimate


class LLMError(RuntimeError):
    """A safe, user-facing provider failure without secret-bearing details."""


@dataclass(frozen=True)
class CompletionResult:
    text: str
    usage: UsageEstimate
    raw: Mapping[str, Any] | None = None


class LLMClient:
    def __init__(self, settings: Settings, *, transport: Callable[..., bytes] | None = None):
        self.settings = settings
        self.counter = TokenCounter(settings.input_cost_per_1k, settings.output_cost_per_1k)
        self._transport = transport

    def complete(self, messages: Sequence[Mapping[str, str]], *, temperature: float = 0.0,
                 max_tokens: int = 512, stop: Sequence[str] | None = None,
                 response_format: Mapping[str, Any] | None = None) -> CompletionResult:
        if not messages:
            raise ValueError("at least one message is required")
        if not 0 <= temperature <= 2:
            raise ValueError("temperature must be between 0 and 2")
        if max_tokens <= 0:
            raise ValueError("max_tokens must be greater than zero")
        payload: dict[str, Any] = {"model": self.settings.model, "messages": list(messages),
                                   "temperature": temperature, "max_tokens": max_tokens}
        if stop:
            payload["stop"] = list(stop)
        if response_format:
            payload["response_format"] = dict(response_format)
            # Groq GPT-OSS requires reasoning output to be hidden or parsed
            # when JSON mode is enabled; hidden keeps the public contract clean.
            payload["reasoning_format"] = "hidden"
            payload["reasoning_effort"] = "low"
        request = urllib.request.Request(
            f"{self.settings.base_url}/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {self.settings.api_key}",
                     "Content-Type": "application/json",
                     "User-Agent": "ecommerce-policy-assistant/0.1"}, method="POST")
        for attempt in range(3):
            try:
                raw_bytes = self._transport(request, self.settings.timeout_seconds) if self._transport else self._send(request)
                raw = json.loads(raw_bytes.decode() if isinstance(raw_bytes, bytes) else raw_bytes)
                text = raw["choices"][0]["message"]["content"].strip()
                provider_usage = raw.get("usage", {})
                usage = UsageEstimate(int(provider_usage.get("prompt_tokens", self.counter.count(json.dumps(messages)))),
                                      int(provider_usage.get("completion_tokens", self.counter.count(text))), 0, 0)
                usage = UsageEstimate(usage.prompt_tokens, usage.completion_tokens,
                                      usage.prompt_tokens + usage.completion_tokens,
                                      round((usage.prompt_tokens / 1000) * self.settings.input_cost_per_1k +
                                            (usage.completion_tokens / 1000) * self.settings.output_cost_per_1k, 8))
                return CompletionResult(text, usage, raw)
            except urllib.error.HTTPError as exc:
                if exc.code in {408, 429, 500, 502, 503, 504} and attempt < 2:
                    time.sleep(0.5 * (2 ** attempt))
                    continue
                raise LLMError(f"language model request failed with HTTP {exc.code}") from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempt < 2:
                    time.sleep(0.5 * (2 ** attempt))
                    continue
                raise LLMError("the language model request timed out or could not connect") from exc
            except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise LLMError("the language model returned an invalid response") from exc

    def _send(self, request: urllib.request.Request) -> bytes:
        try:
            import certifi
            context = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            context = ssl.create_default_context()
        with urllib.request.urlopen(request, timeout=self.settings.timeout_seconds, context=context) as response:
            return response.read()

