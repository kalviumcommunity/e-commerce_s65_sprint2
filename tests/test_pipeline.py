import json
import unittest

from rag_assistant.config import Settings
from rag_assistant.context import ContextAssembler
from rag_assistant.embeddings import EmbeddingClient, EmbeddingRecord
from rag_assistant.generation import GroundedGenerator
from rag_assistant.llm import LLMClient
from rag_assistant.pipeline import RAGPipeline
from rag_assistant.retrieval import Reranker
from rag_assistant.tokens import TokenCounter


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings("secret", "https://provider.test/v1", "model")

    def test_context_preserves_source_boundaries_and_budget(self):
        from rag_assistant.retrieval import RetrievedChunk
        records = [EmbeddingRecord("return in 30 days", (1, 0), {"chunk_id": "a", "source": "returns", "location": "s1"}),
                   EmbeddingRecord("seller warranty", (0, 1), {"chunk_id": "b", "source": "seller", "location": "s2"})]
        context = ContextAssembler(TokenCounter(), 20).build([RetrievedChunk(records[0], .9), RetrievedChunk(records[1], .8)])
        self.assertIn("SOURCE 1", context.text)
        self.assertIn("chunk=a", context.text)
        self.assertLessEqual(context.token_count, 20)

    def test_pipeline_returns_valid_cited_grounded_answer(self):
        def transport(request, timeout):
            body = json.loads(request.data.decode())
            if request.full_url.endswith("/embeddings"):
                return json.dumps({"data": [{"index": 0, "embedding": [1.0, 0.0]}]}).encode()
            return json.dumps({"choices": [{"message": {"content": json.dumps({
                "answer": "Returns are allowed within 30 days.", "status": "answered", "citations": ["policy-1"]
            })}}], "usage": {"prompt_tokens": 10, "completion_tokens": 8}}).encode()
        client = LLMClient(self.settings, transport=transport)
        embedder = EmbeddingClient(self.settings, transport=transport)
        corpus = [EmbeddingRecord("Returns are allowed within 30 days.", (1.0, 0.0),
                                  {"chunk_id": "policy-1", "source": "returns-policy", "location": "section 2"})]
        pipeline = RAGPipeline(embedder, corpus, GroundedGenerator(client), ContextAssembler(TokenCounter(), 100), Reranker())
        answer = pipeline.answer("How long do I have to return it?")
        self.assertEqual(answer.status, "answered")
        self.assertEqual(answer.citations[0].chunk_id, "policy-1")

    def test_invalid_citation_is_rejected(self):
        from rag_assistant.context import Context
        from rag_assistant.retrieval import RetrievedChunk
        def transport(request, timeout):
            return json.dumps({"choices": [{"message": {"content": '{"answer":"x","status":"answered","citations":["wrong"]}'}}]}).encode()
        generator = GroundedGenerator(LLMClient(self.settings, transport=transport))
        record = EmbeddingRecord("evidence", (1,), {"chunk_id": "right", "source": "s"})
        with self.assertRaises(ValueError):
            generator.generate("q", Context("evidence", (RetrievedChunk(record, 1),), 1))


if __name__ == "__main__":
    unittest.main()

