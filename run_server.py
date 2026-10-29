from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from rag_assistant.config import Settings
from rag_assistant.context import ContextAssembler
from rag_assistant.embeddings import LocalEmbeddingClient
from rag_assistant.generation import GroundedGenerator
from rag_assistant.guardrails import EvidenceGate, FollowUpRewriter
from rag_assistant.ingestion import Chunker, DocumentLoader
from rag_assistant.llm import LLMClient
from rag_assistant.pipeline import RAGPipeline
from rag_assistant.retrieval import Reranker
from rag_assistant.service import DocumentRegistry, RAGService, serve
from rag_assistant.tokens import TokenCounter


def build_service() -> RAGService:
    """Connect every backend component and return the application service.

    Interview explanation: this function is the composition root. It loads the
    approved policies, makes them searchable, connects the Groq LLM to the RAG
    pipeline, and exposes that pipeline to the web/API service.
    """
    # Runtime configuration validates the Groq key, model, timeout, context
    # size, and optional cost values before the server accepts requests.
    settings = Settings.from_env()
    llm = LLMClient(settings)
    sample_dir = Path(__file__).parent / "data" / "sample"
    loader = DocumentLoader()
    # One hundred words keeps passages focused; overlap preserves facts that
    # cross a chunk boundary.
    chunker = Chunker(max_words=100, overlap_words=15)
    documents = []
    all_chunks = []
    # 1. Load each approved policy and split it into small, traceable passages.
    for sample_path in sorted(sample_dir.iterdir()):
        if sample_path.suffix.lower() not in DocumentLoader.SUPPORTED:
            continue
        document_id = sample_path.stem.replace("_", "-")
        document = loader.load(sample_path.name, sample_path.read_text(),
                               document_id=document_id, version="v1")
        chunks = chunker.chunk(document)
        documents.append((document_id, chunks))
        all_chunks.extend(chunks)

    # 2. Convert every passage into a local vector used for semantic retrieval.
    embedder = LocalEmbeddingClient()
    corpus = embedder.embed([chunk.text for chunk in all_chunks], [chunk.metadata for chunk in all_chunks])

    # 3. Assemble the complete question -> retrieval -> answer RAG workflow.
    pipeline = RAGPipeline(
        embeddings=embedder,
        corpus=corpus,
        # GroundedGenerator calls Groq only after retrieval has supplied evidence.
        generator=GroundedGenerator(llm),
        # Reserve model-output space and fit the strongest passages in the rest.
        context=ContextAssembler(TokenCounter(), max(1000, settings.context_window - 1024)),
        # Reranking improves precision after the broader vector search.
        reranker=Reranker(),
        # A low but explicit threshold blocks clearly unrelated questions.
        evidence_gate=EvidenceGate(minimum_score=0.15),
        # Follow-up rewriting turns questions such as "What about opened ones?"
        # into a standalone search query using recent conversation history.
        follow_up_rewriter=FollowUpRewriter(llm),
    )

    # 4. Track which document versions are active and available to the UI.
    registry = DocumentRegistry()
    for document_id, chunks in documents:
        registry.activate(document_id, "v1", chunks)
    return RAGService(pipeline, registry=registry)


if __name__ == "__main__":
    # Secrets stay outside the codebase and are read from the local environment.
    load_dotenv()
    # PORT supports local execution and hosting platforms without code changes.
    port = int(os.getenv("PORT", "8000"))
    print(f"Groq policy assistant running at http://127.0.0.1:{port}")
    serve(build_service(), port=port)

