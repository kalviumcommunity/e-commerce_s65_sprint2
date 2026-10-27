import unittest

from rag_assistant.embeddings import LocalEmbeddingClient, lexical_embedding


class LocalEmbeddingTests(unittest.TestCase):
    def test_local_client_is_embedding_compatible(self):
        records = LocalEmbeddingClient(64).embed(["return policy"], [{"chunk_id": "x"}])
        self.assertEqual(len(records), 1)
        self.assertEqual(len(records[0].vector), 64)
        self.assertEqual(records[0].metadata["chunk_id"], "x")

    def test_shared_terms_have_nonzero_similarity_signal(self):
        left = lexical_embedding("return policy")
        right = lexical_embedding("return refund")
        self.assertGreater(sum(a * b for a, b in zip(left, right)), 0)


if __name__ == "__main__":
    unittest.main()
