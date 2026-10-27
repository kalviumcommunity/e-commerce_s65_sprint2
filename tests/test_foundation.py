import json
import os
import unittest
from unittest.mock import patch

from rag_assistant.config import ConfigurationError, Settings
from rag_assistant.llm import LLMClient, LLMError
from rag_assistant.tokens import TokenCounter


class FoundationTests(unittest.TestCase):
    def test_missing_configuration_is_helpful(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ConfigurationError, "GROQ_API_KEY"):
                Settings.from_env()

    def test_groq_configuration_is_fixed_to_groq_endpoint(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "secret", "GROQ_MODEL": "openai/gpt-oss-20b"}, clear=True):
            settings = Settings.from_env()
        self.assertEqual(settings.base_url, "https://api.groq.com/openai/v1")
        self.assertEqual(settings.model, "openai/gpt-oss-20b")

    def test_token_estimate_and_budget(self):
        counter = TokenCounter(1, 2)
        estimate = counter.estimate("hello world", "answer")
        self.assertEqual(estimate.total_tokens, estimate.prompt_tokens + estimate.completion_tokens)
        self.assertLessEqual(counter.count(counter.trim_to_budget("a" * 100, 5)), 6)

    def test_completion_success_and_usage(self):
        settings = Settings("secret", "https://provider.test/v1", "model", 3, 1, 2, 100)
        def transport(request, timeout):
            self.assertEqual(timeout, 3)
            self.assertEqual(request.headers["Authorization"], "Bearer secret")
            return json.dumps({"choices": [{"message": {"content": "  grounded answer  "}}],
                               "usage": {"prompt_tokens": 4, "completion_tokens": 3}}).encode()
        result = LLMClient(settings, transport=transport).complete([{"role": "user", "content": "question"}])
        self.assertEqual(result.text, "grounded answer")
        self.assertEqual(result.usage.total_tokens, 7)

    def test_malformed_provider_response_is_safe(self):
        settings = Settings("secret", "https://provider.test/v1", "model")
        with self.assertRaises(LLMError):
            LLMClient(settings, transport=lambda *_: b"{}") .complete([{"role": "user", "content": "q"}])


if __name__ == "__main__":
    unittest.main()

