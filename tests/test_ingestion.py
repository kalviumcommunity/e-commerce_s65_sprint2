import unittest

from rag_assistant.embeddings import EmbeddingRecord
from rag_assistant.ingestion import Chunker, DocumentLoader, InMemoryVectorStore, IngestionError


class IngestionTests(unittest.TestCase):
    def test_loader_normalizes_and_rejects_unsupported_input(self):
        document = DocumentLoader().load("policy.md", "  returns   are allowed\nwithin 30 days ", document_id="returns", version="v1")
        self.assertEqual(document.text, "returns are allowed\nwithin 30 days")
        with self.assertRaises(IngestionError):
            DocumentLoader().load("policy.exe", "data", document_id="x", version="v1")

    def test_chunking_preserves_stable_metadata_and_overlap(self):
        document = DocumentLoader().load("policy.txt", "one two three four five six seven", document_id="returns", version="v1")
        chunks = Chunker(max_words=4, overlap_words=1).chunk(document)
        self.assertEqual(chunks[0].chunk_id, "returns:v1:chunk-0000")
        self.assertIn("four", chunks[0].text)
        self.assertIn("four", chunks[1].text)

    def test_vector_store_supports_metadata_filter_and_hybrid_search(self):
        store = InMemoryVectorStore()
        store.upsert([EmbeddingRecord("return policy", (1, 0), {"chunk_id": "a", "document_id": "returns"}),
                      EmbeddingRecord("shipping policy", (0, 1), {"chunk_id": "b", "document_id": "shipping"})])
        self.assertEqual(store.search((1, 0), document_id="returns")[0].record.metadata["chunk_id"], "a")
        self.assertEqual(store.hybrid_search("shipping", (0, 1))[0].record.metadata["chunk_id"], "b")


if __name__ == "__main__":
    unittest.main()

