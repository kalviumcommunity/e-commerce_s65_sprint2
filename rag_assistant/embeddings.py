from __future__ import annotations

import hashlib
import json
import math
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from .config import Settings


class EmbeddingError(RuntimeError):
    pass


@dataclass(frozen=True)
class EmbeddingRecord:
    text: str
    vector: tuple[float, ...]
    metadata: Mapping[str, Any]


class EmbeddingClient:
    def __init__(self, settings: Settings, *, model: str | None = None,
                 batch_size: int = 64, transport: Callable[..., bytes] | None = None):
        self.settings = settings
        self.model = model or settings.model
        self.batch_size = batch_size
        self._transport = transport
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than zero")

    def embed(self, texts: Sequence[str], metadata: Sequence[Mapping[str, Any]] | None = None) -> list[EmbeddingRecord]:
        if len(texts) != len(set(texts)):
            raise ValueError("duplicate texts must be removed before embedding")
        if any(not text.strip() for text in texts):
            raise ValueError("embedding text cannot be empty")
        if metadata is None:
            metadata = [{} for _ in texts]
        if len(metadata) != len(texts):
            raise ValueError("metadata must have one entry per text")
        records: list[EmbeddingRecord] = []
        for start in range(0, len(texts), self.batch_size):
            batch = list(texts[start:start + self.batch_size])
            vectors = self._request(batch)
            if len(vectors) != len(batch):
                raise EmbeddingError("embedding provider returned the wrong number of vectors")
            records.extend(EmbeddingRecord(text, tuple(vector), metadata[start + i])
                           for i, (text, vector) in enumerate(zip(batch, vectors)))
        return records

    def _request(self, texts: list[str]) -> list[list[float]]:
        payload = json.dumps({"model": self.model, "input": texts}).encode()
        request = urllib.request.Request(f"{self.settings.base_url}/embeddings", data=payload,
                                         headers={"Authorization": f"Bearer {self.settings.api_key}",
                                                  "Content-Type": "application/json",
                                                  "User-Agent": "ecommerce-policy-assistant/0.1"}, method="POST")
        try:
            raw_bytes = self._transport(request, self.settings.timeout_seconds) if self._transport else self._send(request)
            raw = json.loads(raw_bytes.decode() if isinstance(raw_bytes, bytes) else raw_bytes)
            data = sorted(raw["data"], key=lambda row: row["index"])
            return [row["embedding"] for row in data]
        except urllib.error.HTTPError as exc:
            raise EmbeddingError(f"embedding request failed with HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise EmbeddingError("embedding request timed out or could not connect") from exc
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise EmbeddingError("embedding provider returned an invalid response") from exc

    def _send(self, request: urllib.request.Request) -> bytes:
        with urllib.request.urlopen(request, timeout=self.settings.timeout_seconds) as response:
            return response.read()


def deterministic_embedding(text: str, dimensions: int = 32) -> tuple[float, ...]:
    """Stable offline vector for tests and local demos, not a semantic model."""
    if dimensions <= 0:
        raise ValueError("dimensions must be greater than zero")
    digest = hashlib.sha256(text.encode()).digest()
    return tuple((digest[i % len(digest)] / 127.5) - 1 for i in range(dimensions))


def lexical_embedding(text: str, dimensions: int = 256) -> tuple[float, ...]:
    """Small local bag-of-words vector for a no-second-provider deployment."""
    if dimensions <= 0:
        raise ValueError("dimensions must be greater than zero")
    vector = [0.0] * dimensions
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        digest = hashlib.sha256(token.encode()).digest()
        vector[int.from_bytes(digest[:4], "big") % dimensions] += 1.0
    norm = math.sqrt(sum(value * value for value in vector))
    return tuple(value / norm for value in vector) if norm else tuple(vector)


class LocalEmbeddingClient:
    """Embedding-compatible client used locally because Groq is generation-only here."""

    def __init__(self, dimensions: int = 256):
        self.dimensions = dimensions

    def embed(self, texts: Sequence[str], metadata: Sequence[Mapping[str, Any]] | None = None) -> list[EmbeddingRecord]:
        if metadata is None:
            metadata = [{} for _ in texts]
        if len(texts) != len(metadata):
            raise ValueError("metadata must have one entry per text")
        return [EmbeddingRecord(text, lexical_embedding(text, self.dimensions), meta)
                for text, meta in zip(texts, metadata)]

