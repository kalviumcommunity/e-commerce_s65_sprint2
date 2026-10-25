from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .retrieval import RetrievedChunk
from .tokens import TokenCounter


@dataclass(frozen=True)
class Context:
    text: str
    chunks: tuple[RetrievedChunk, ...]
    token_count: int


class ContextAssembler:
    def __init__(self, counter: TokenCounter, max_tokens: int):
        self.counter = counter
        self.max_tokens = max_tokens

    def build(self, chunks: Sequence[RetrievedChunk]) -> Context:
        selected: list[RetrievedChunk] = []
        sections: list[str] = []
        used = 0
        for index, chunk in enumerate(chunks, 1):
            metadata = chunk.record.metadata
            source = metadata.get("source") or metadata.get("document_id") or "unknown-source"
            location = metadata.get("location") or metadata.get("section") or "unknown-location"
            section = f"[SOURCE {index} | {source} | {location} | chunk={metadata.get('chunk_id', index)}]\n{chunk.record.text}"
            cost = self.counter.count(section)
            if used + cost > self.max_tokens:
                break
            selected.append(chunk)
            sections.append(section)
            used += cost
        return Context("\n\n".join(sections), tuple(selected), used)

