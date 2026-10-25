from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .context import ContextAssembler
from .embeddings import EmbeddingClient, EmbeddingRecord
from .generation import GroundedAnswer, GroundedGenerator
from .retrieval import Reranker, rank_by_similarity
from .guardrails import EvidenceGate, FollowUpRewriter


@dataclass
class RAGPipeline:
    embeddings: EmbeddingClient
    corpus: Sequence[EmbeddingRecord]
    generator: GroundedGenerator
    context: ContextAssembler
    reranker: Reranker
    top_k: int = 8
    evidence_gate: EvidenceGate | None = None
    follow_up_rewriter: FollowUpRewriter | None = None

    def answer(self, question: str, history: Sequence[dict[str, str]] | None = None) -> GroundedAnswer:
        if not question.strip():
            raise ValueError("question cannot be empty")
        retrieval_question = self.follow_up_rewriter.rewrite(question, history or []) if self.follow_up_rewriter else question
        query = self.embeddings.embed([retrieval_question])[0].vector
        candidates = rank_by_similarity(query, self.corpus, self.top_k)
        reranked = self.reranker.rerank(question, candidates, top_k=self.top_k)
        if self.evidence_gate:
            decision = self.evidence_gate.assess(reranked)
            if not decision.allowed:
                return self.evidence_gate.refusal(decision.reason)
        return self.generator.generate(question, self.context.build(reranked))

