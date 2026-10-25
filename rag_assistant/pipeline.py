from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .context import ContextAssembler
from .embeddings import EmbeddingClient, EmbeddingRecord
from .generation import GroundedAnswer, GroundedGenerator
from .retrieval import Reranker, rank_by_similarity


@dataclass
class RAGPipeline:
    embeddings: EmbeddingClient
    corpus: Sequence[EmbeddingRecord]
    generator: GroundedGenerator
    context: ContextAssembler
    reranker: Reranker
    top_k: int = 8

    def answer(self, question: str) -> GroundedAnswer:
        if not question.strip():
            raise ValueError("question cannot be empty")
        query = self.embeddings.embed([question])[0].vector
        candidates = rank_by_similarity(query, self.corpus, self.top_k)
        reranked = self.reranker.rerank(question, candidates, top_k=self.top_k)
        return self.generator.generate(question, self.context.build(reranked))

