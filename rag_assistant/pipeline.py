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
    """Orchestrate the complete online Retrieval-Augmented Generation flow.

    Data flow for an interview walkthrough:
    question/history -> standalone retrieval query -> local embedding ->
    similarity ranking -> lexical reranking -> evidence gate -> token-bounded
    context -> Groq JSON answer -> validated citations.
    """

    # Same embedding interface is used for both documents and user questions.
    embeddings: EmbeddingClient
    # Corpus contains searchable passage vectors plus citation metadata.
    corpus: Sequence[EmbeddingRecord]
    # Generator owns the grounded prompt and strict response validation.
    generator: GroundedGenerator
    # Context assembler protects the model's maximum context window.
    context: ContextAssembler
    # Reranker sharpens the initial broad similarity results.
    reranker: Reranker
    # top_k limits latency and the amount of evidence considered downstream.
    top_k: int = 8
    # Optional components make the pipeline testable in small isolated pieces.
    evidence_gate: EvidenceGate | None = None
    follow_up_rewriter: FollowUpRewriter | None = None

    def answer(self, question: str, history: Sequence[dict[str, str]] | None = None) -> GroundedAnswer:
        """Answer one question using retrieved evidence instead of model memory.

        Interview explanation: this method is the heart of RAG. It converts the
        question into a search vector, finds and reranks policy passages, checks
        that the evidence is strong enough, then asks the LLM to answer only
        from that evidence.
        """
        if not question.strip():
            raise ValueError("question cannot be empty")

        # Include previous chat context when the user asks a follow-up question.
        retrieval_question = self.follow_up_rewriter.rewrite(question, history or []) if self.follow_up_rewriter else question

        # Retrieve passages whose vectors are most similar to the question.
        query = self.embeddings.embed([retrieval_question])[0].vector
        candidates = rank_by_similarity(query, self.corpus, self.top_k)

        # Promote passages containing the most useful exact terms and context.
        reranked = self.reranker.rerank(retrieval_question, candidates, top_k=self.top_k)

        # Refuse safely when the documents do not contain reliable evidence.
        if self.evidence_gate:
            decision = self.evidence_gate.assess(reranked)
            if not decision.allowed:
                return self.evidence_gate.refusal(decision.reason)

        # Fit the evidence into the context window and generate a cited answer.
        return self.generator.generate(question, self.context.build(reranked))

