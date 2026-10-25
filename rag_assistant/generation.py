from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .context import Context
from .llm import CompletionResult, LLMClient


@dataclass(frozen=True)
class Citation:
    chunk_id: str
    document: str
    location: str
    excerpt: str
    score: float


@dataclass(frozen=True)
class GroundedAnswer:
    answer: str
    status: str
    citations: tuple[Citation, ...]
    usage: Any | None = None


class GroundedGenerator:
    def __init__(self, client: LLMClient):
        self.client = client

    def generate(self, question: str, context: Context) -> GroundedAnswer:
        if not context.chunks:
            return GroundedAnswer("I don’t have enough approved evidence to answer that.", "insufficient_evidence", ())
        system = (
            "Answer only from the supplied evidence. Do not use model memory. "
            "Return JSON with keys answer, status, and citations. citations must be an array "
            "of chunk_id values copied from the supplied source headers. If evidence is insufficient, "
            "use status insufficient_evidence and do not invent a claim."
        )
        user = f"Question: {question}\n\nEvidence:\n{context.text}"
        result = self.client.complete([{"role": "system", "content": system}, {"role": "user", "content": user}],
                                      temperature=0, max_tokens=512)
        return self._parse(result, context)

    def _parse(self, result: CompletionResult, context: Context) -> GroundedAnswer:
        try:
            payload: Mapping[str, Any] = json.loads(result.text)
            answer = str(payload["answer"]).strip()
            status = str(payload.get("status", "answered"))
            ids = payload.get("citations", [])
            if not answer or status not in {"answered", "needs_clarification", "insufficient_evidence"}:
                raise ValueError
            if not isinstance(ids, list):
                raise ValueError
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError("model returned an invalid grounded-answer contract") from exc
        by_id = {str(c.record.metadata.get("chunk_id")): c for c in context.chunks}
        citations: list[Citation] = []
        for chunk_id in ids:
            chunk = by_id.get(str(chunk_id))
            if chunk is None:
                raise ValueError("model cited a chunk outside the retrieved context")
            metadata = chunk.record.metadata
            citations.append(Citation(str(chunk_id), str(metadata.get("source", "unknown-source")),
                                      str(metadata.get("location", "unknown-location")), chunk.record.text,
                                      chunk.score))
        if status == "answered" and not citations:
            raise ValueError("answered response must contain at least one valid citation")
        return GroundedAnswer(answer, status, tuple(citations), result.usage)

