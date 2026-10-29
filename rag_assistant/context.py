"""Build a source-labelled evidence block that fits the model context limit."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .retrieval import RetrievedChunk
from .tokens import TokenCounter


@dataclass(frozen=True)
class Context:
    """The exact evidence sent to the LLM plus its source chunk objects."""
    text: str
    chunks: tuple[RetrievedChunk, ...]
    token_count: int


class ContextAssembler:
    """Select high-ranking passages without exceeding the token budget."""

    def __init__(self, counter: TokenCounter, max_tokens: int):
        self.counter = counter
        self.max_tokens = max_tokens

    def build(self, chunks: Sequence[RetrievedChunk]) -> Context:
        """Add ranked chunks until the next chunk would exceed the budget."""
        selected: list[RetrievedChunk] = []
        sections: list[str] = []
        used = 0
        for index, chunk in enumerate(chunks, 1):
            metadata = chunk.record.metadata
            # Labels preserve provenance inside the prompt and give the model a
            # stable chunk ID that can be returned as a citation.
            source = metadata.get("source") or metadata.get("document_id") or "unknown-source"
            location = metadata.get("location") or metadata.get("section") or "unknown-location"
            section = f"[SOURCE {index} | {source} | {location} | chunk={metadata.get('chunk_id', index)}]\n{chunk.record.text}"
            cost = self.counter.count(section)
            # Chunks are already relevance-ranked, so stopping here retains the
            # strongest available evidence within the context window.
            if used + cost > self.max_tokens:
                break
            selected.append(chunk)
            sections.append(section)
            used += cost
        return Context("\n\n".join(sections), tuple(selected), used)

