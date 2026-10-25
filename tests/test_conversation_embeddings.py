import json
import unittest

from rag_assistant.config import Settings
from rag_assistant.conversation import Conversation
from rag_assistant.embeddings import EmbeddingClient, EmbeddingError, deterministic_embedding
from rag_assistant.tokens import TokenCounter


class ConversationEmbeddingTests(unittest.TestCase):
    def test_history_keeps_recent_messages_inside_budget(self):
        conversation = Conversation(TokenCounter(), context_window=24, reserved_output_tokens=4)
        for i in range(8):
            conversation.add("user", f"old question {i} with extra words")
        messages = conversation.prompt_messages("Answer only from evidence")
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[-1]["content"], "old question 7 with extra words")
        self.assertLessEqual(sum(TokenCounter.count(m["content"]) for m in messages), 20)

    def test_embedding_batches_and_preserves_metadata(self):
        calls = []
        settings = Settings("secret", "https://provider.test/v1", "embed-model")
        def transport(request, timeout):
            body = json.loads(request.data.decode())
            calls.append(body["input"])
            return json.dumps({"data": [{"index": i, "embedding": [float(i), 1.0]}
                                         for i in range(len(body["input"]))]}).encode()
        records = EmbeddingClient(settings, batch_size=2, transport=transport).embed(
            ["one", "two", "three"], [{"id": 1}, {"id": 2}, {"id": 3}])
        self.assertEqual(len(calls), 2)
        self.assertEqual(records[2].metadata["id"], 3)
        self.assertEqual(records[1].vector, (1.0, 1.0))

    def test_invalid_embedding_response_is_safe(self):
        settings = Settings("secret", "https://provider.test/v1", "embed-model")
        with self.assertRaises(EmbeddingError):
            EmbeddingClient(settings, transport=lambda *_: b"{}").embed(["one"])

    def test_local_embedding_is_stable_and_sized(self):
        self.assertEqual(deterministic_embedding("policy", 8), deterministic_embedding("policy", 8))
        self.assertEqual(len(deterministic_embedding("policy", 8)), 8)


if __name__ == "__main__":
    unittest.main()

