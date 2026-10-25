import unittest
from unittest.mock import Mock

from rag_assistant.embeddings import EmbeddingRecord
from rag_assistant.retrieval import BatchEmbeddingRunner, Reranker, cosine_similarity, rank_by_similarity


def record(text, vector):
    return EmbeddingRecord(text, tuple(vector), {"source": text})


class RetrievalTests(unittest.TestCase):
    def test_cosine_and_rank_are_deterministic(self):
        self.assertAlmostEqual(cosine_similarity([1, 0], [1, 0]), 1.0)
        ranked = rank_by_similarity([1, 0], [record("wrong", [0, 1]), record("right", [1, 0])])
        self.assertEqual(ranked[0].record.text, "right")

    def test_batch_runner_skips_completed_and_tracks_usage(self):
        client = Mock()
        client.embed.return_value = [record("one", [1, 0]), record("two", [0, 1])]
        runner = BatchEmbeddingRunner(client, sleep=lambda _: None)
        first = runner.run(["one", "two"], [{}, {}])
        second = runner.run(["one", "two"], [{}, {}])
        self.assertEqual(len(first), 2)
        self.assertEqual(len(second), 2)
        self.assertEqual(client.embed.call_count, 1)
        self.assertEqual(runner.usage.skipped_duplicates, 2)

    def test_batch_runner_retries_transient_failure(self):
        client = Mock()
        client.embed.side_effect = [RuntimeError("rate limit"), [record("one", [1, 0])]]
        runner = BatchEmbeddingRunner(client, max_retries=2, sleep=lambda _: None)
        runner.run(["one"])
        self.assertEqual(client.embed.call_count, 2)
        self.assertEqual(runner.usage.retries, 1)

    def test_reranker_promotes_exact_terms(self):
        candidates = [
            __import__("rag_assistant.retrieval", fromlist=["RetrievedChunk"]).RetrievedChunk(record("refund window", [1, 0]), .9),
            __import__("rag_assistant.retrieval", fromlist=["RetrievedChunk"]).RetrievedChunk(record("shipping address", [1, 0]), .95),
        ]
        result = Reranker().rerank("refund", candidates)
        self.assertEqual(result[0].record.text, "refund window")


if __name__ == "__main__":
    unittest.main()

