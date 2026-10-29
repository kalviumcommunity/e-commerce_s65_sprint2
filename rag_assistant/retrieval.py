"""Rank embedded policy chunks and improve precision with reranking."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from .embeddings import EmbeddingClient, EmbeddingRecord
from .tokens import TokenCounter


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    """Measure vector direction similarity on the conventional -1..1 scale."""
    if len(left) != len(right) or not left:
        raise ValueError("vectors must be non-empty and have equal dimensions")
    denominator = math.sqrt(sum(x * x for x in left)) * math.sqrt(sum(y * y for y in right))
    return 0.0 if denominator == 0 else sum(x * y for x, y in zip(left, right)) / denominator


@dataclass(frozen=True)
class RetrievedChunk:
    """A source record paired with its current retrieval/reranking score."""
    record: EmbeddingRecord
    score: float


def rank_by_similarity(query: Sequence[float], records: Sequence[EmbeddingRecord], top_k: int = 5) -> list[RetrievedChunk]:
    """Select the top-k corpus passages most similar to the query vector."""
    if top_k <= 0:
        raise ValueError("top_k must be greater than zero")
    ranked = [RetrievedChunk(record, cosine_similarity(query, record.vector)) for record in records]
    return sorted(ranked, key=lambda item: item.score, reverse=True)[:top_k]


@dataclass(frozen=True)
class EmbeddingUsage:
    """Operational counters for a batch embedding run."""
    attempted: int
    embedded: int
    skipped_duplicates: int
    retries: int
    input_tokens: int


class BatchEmbeddingRunner:
    """Resumable embedding runner; completed text keys are never requested twice."""

    def __init__(self, client: EmbeddingClient, *, max_retries: int = 3,
                 sleep: Callable[[float], None] = time.sleep):
        self.client = client
        self.max_retries = max_retries
        self.sleep = sleep
        self.completed: dict[str, EmbeddingRecord] = {}
        self.usage = EmbeddingUsage(0, 0, 0, 0, 0)

    def run(self, texts: Sequence[str], metadata: Sequence[Mapping] | None = None) -> list[EmbeddingRecord]:
        """Embed new texts, skip completed work, and retry transient failures."""
        if metadata is None:
            metadata = [{} for _ in texts]
        if len(metadata) != len(texts):
            raise ValueError("metadata must have one entry per text")
        unique: list[str] = []
        unique_meta: list[Mapping] = []
        skipped = 0
        for text, meta in zip(texts, metadata):
            if text in self.completed:
                skipped += 1
            elif text not in unique:
                unique.append(text)
                unique_meta.append(meta)
            else:
                skipped += 1
        retries = 0
        new_records: list[EmbeddingRecord] = []
        if unique:
            # Exponential backoff prevents immediate repeated provider pressure.
            for attempt in range(self.max_retries + 1):
                try:
                    new_records = self.client.embed(unique, unique_meta)
                    break
                except Exception:
                    if attempt >= self.max_retries:
                        raise
                    retries += 1
                    self.sleep(2 ** attempt)
        for record in new_records:
            self.completed[record.text] = record
        counter = TokenCounter()
        self.usage = EmbeddingUsage(len(texts), len(new_records), skipped, retries,
                                    sum(counter.count(text) for text in unique))
        return [self.completed[text] for text in texts if text in self.completed]


class Reranker:
    """Reorder a retrieved candidate set using a precision-oriented scorer."""

    def __init__(self, scorer: Callable[[str, str], float] | None = None):
        self.scorer = scorer or self._lexical_score

    @staticmethod
    def _lexical_score(query: str, text: str) -> float:
        query_words = set(query.lower().split())
        text_words = set(text.lower().split())
        return len(query_words & text_words) / max(1, len(query_words))

    def rerank(self, query: str, candidates: Sequence[RetrievedChunk], *, top_k: int = 5) -> list[RetrievedChunk]:
        """Score only retrieved candidates and keep the strongest passages."""
        rescored = [RetrievedChunk(item.record, self.scorer(query, item.record.text)) for item in candidates]
        return sorted(rescored, key=lambda item: item.score, reverse=True)[:top_k]

