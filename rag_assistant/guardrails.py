from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Sequence

from .generation import GroundedAnswer
from .llm import LLMClient
from .retrieval import RetrievedChunk


@dataclass(frozen=True)
class EvidenceDecision:
    allowed: bool
    reason: str


class EvidenceGate:
    def __init__(self, *, minimum_score: float = 0.25, minimum_chunks: int = 1):
        self.minimum_score = minimum_score
        self.minimum_chunks = minimum_chunks

    def assess(self, candidates: Sequence[RetrievedChunk]) -> EvidenceDecision:
        if len(candidates) < self.minimum_chunks:
            return EvidenceDecision(False, "no supporting evidence was retrieved")
        if max(chunk.score for chunk in candidates) < self.minimum_score:
            return EvidenceDecision(False, "retrieved evidence is below the confidence threshold")
        return EvidenceDecision(True, "evidence threshold satisfied")

    def refusal(self, reason: str) -> GroundedAnswer:
        return GroundedAnswer("I don’t have enough approved evidence to answer that safely. "
                              "Please rephrase the question or provide the relevant policy.",
                              "insufficient_evidence", ())


class FollowUpRewriter:
    """Turns an elliptical follow-up into a standalone retrieval query."""

    def __init__(self, client: LLMClient):
        self.client = client

    def rewrite(self, question: str, history: Sequence[dict[str, str]]) -> str:
        if not history:
            return question
        messages = [{"role": "system", "content":
                     "Rewrite the latest user question as a standalone search query using only conversation context. "
                     "Return JSON exactly as {\"query\": \"...\"}. Do not answer the question."}]
        messages.extend(history[-8:])
        messages.append({"role": "user", "content": question})
        result = self.client.complete(messages, temperature=0, max_tokens=128)
        try:
            query = str(json.loads(result.text)["query"]).strip()
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError("follow-up rewriter returned an invalid query contract") from exc
        if not query:
            raise ValueError("follow-up rewriter returned an empty query")
        return query

