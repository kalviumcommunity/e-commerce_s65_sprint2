import json
import unittest

from rag_assistant.config import Settings
from rag_assistant.embeddings import EmbeddingClient, EmbeddingRecord
from rag_assistant.context import ContextAssembler
from rag_assistant.generation import GroundedGenerator
from rag_assistant.guardrails import EvidenceGate, FollowUpRewriter
from rag_assistant.llm import LLMClient
from rag_assistant.pipeline import RAGPipeline
from rag_assistant.retrieval import Reranker, RetrievedChunk
from rag_assistant.tokens import TokenCounter


class GuardrailTests(unittest.TestCase):
    def test_weak_evidence_is_refused(self):
        gate = EvidenceGate(minimum_score=.8)
        decision = gate.assess([RetrievedChunk(EmbeddingRecord("x", (1,), {}), .2)])
        self.assertFalse(decision.allowed)
        self.assertEqual(gate.refusal(decision.reason).status, "insufficient_evidence")

    def test_follow_up_is_rewritten_with_history(self):
        settings = Settings("secret", "https://provider.test/v1", "model")
        def transport(request, timeout):
            return json.dumps({"choices": [{"message": {"content": '{"query":"return policy electronics window"}'}}]}).encode()
        query = FollowUpRewriter(LLMClient(settings, transport=transport)).rewrite(
            "How long is it?", [{"role": "user", "content": "What is the electronics return policy?"}])
        self.assertIn("electronics", query)

    def test_pipeline_refuses_before_generation_when_evidence_is_weak(self):
        settings = Settings("secret", "https://provider.test/v1", "model")
        calls = []
        def transport(request, timeout):
            calls.append(request.full_url)
            if request.full_url.endswith("/embeddings"):
                return json.dumps({"data": [{"index": 0, "embedding": [1.0, 0.0]}]}).encode()
            return json.dumps({"choices": [{"message": {"content": '{"answer":"bad","status":"answered","citations":["x"]}'}}]}).encode()
        corpus = [EmbeddingRecord("unrelated", (0.0, 1.0), {"chunk_id": "x", "source": "s"})]
        pipeline = RAGPipeline(EmbeddingClient(settings, transport=transport), corpus,
                               GroundedGenerator(LLMClient(settings, transport=transport)),
                               ContextAssembler(TokenCounter(), 100), Reranker(), evidence_gate=EvidenceGate(minimum_score=.8))
        result = pipeline.answer("question")
        self.assertEqual(result.status, "insufficient_evidence")
        self.assertEqual(len([url for url in calls if url.endswith("/chat/completions")]), 0)


if __name__ == "__main__":
    unittest.main()

