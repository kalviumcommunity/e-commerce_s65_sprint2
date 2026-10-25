import unittest
from unittest.mock import Mock

from rag_assistant.generation import GroundedAnswer
from rag_assistant.service import DocumentRegistry, RAGService, ResponseCache


class ServiceTests(unittest.TestCase):
    def test_query_response_is_cached_and_has_request_metadata(self):
        pipeline = Mock()
        pipeline.answer.return_value = GroundedAnswer("answer", "answered", ())
        service = RAGService(pipeline, cache=ResponseCache(60))
        first = service.query("q")
        second = service.query("q")
        self.assertFalse(first["cached"])
        self.assertTrue(second["cached"])
        self.assertEqual(pipeline.answer.call_count, 1)
        self.assertIn("request_id", first)

    def test_upload_rejects_empty_activation(self):
        pipeline = Mock()
        service = RAGService(pipeline, registry=DocumentRegistry())
        result = service.upload("policy.txt", "return in 30 days", document_id="returns", version="v1")
        self.assertEqual(result["status"], "active")


if __name__ == "__main__":
    unittest.main()

