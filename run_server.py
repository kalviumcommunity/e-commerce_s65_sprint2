from __future__ import annotations

from pathlib import Path

from rag_assistant.config import Settings
from rag_assistant.context import ContextAssembler
from rag_assistant.embeddings import LocalEmbeddingClient
from rag_assistant.generation import GroundedGenerator
from rag_assistant.guardrails import EvidenceGate, FollowUpRewriter
from rag_assistant.ingestion import Chunker, DocumentLoader
from rag_assistant.llm import LLMClient
from rag_assistant.pipeline import RAGPipeline
from rag_assistant.retrieval import Reranker
from rag_assistant.service import RAGService, serve
from rag_assistant.tokens import TokenCounter


def build_service() -> RAGService:
    settings = Settings.from_env()
    llm = LLMClient(settings)
    sample_path = Path(__file__).parent / "data" / "sample" / "return_policy.md"
    document = DocumentLoader().load(
        sample_path.name, sample_path.read_text(), document_id="return-policy", version="v1"
    )
    chunks = Chunker(max_words=100, overlap_words=15).chunk(document)
    embedder = LocalEmbeddingClient()
    corpus = embedder.embed([chunk.text for chunk in chunks], [chunk.metadata for chunk in chunks])
    pipeline = RAGPipeline(
        embeddings=embedder,
        corpus=corpus,
        generator=GroundedGenerator(llm),
        context=ContextAssembler(TokenCounter(), max(1000, settings.context_window - 1024)),
        reranker=Reranker(),
        evidence_gate=EvidenceGate(minimum_score=0.15),
        follow_up_rewriter=FollowUpRewriter(llm),
    )
    return RAGService(pipeline)


if __name__ == "__main__":
    print("Groq policy assistant running at http://127.0.0.1:8000")
    serve(build_service())

