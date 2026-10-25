import unittest

from rag_assistant.embeddings import EmbeddingRecord
from rag_assistant.evaluation import evaluate_answer, evaluate_retrieval
from rag_assistant.generation import Citation, GroundedAnswer
from rag_assistant.prompts import GROUNDED_ANSWER, parse_structured_json
from rag_assistant.retrieval import RetrievedChunk


class EvaluationPromptTests(unittest.TestCase):
    def test_prompt_template_and_json_contract(self):
        self.assertIn("policy", GROUNDED_ANSWER.render(context="evidence", question="q"))
        self.assertEqual(parse_structured_json('{"answer":"x"}', required=["answer"])["answer"], "x")
        with self.assertRaises(ValueError):
            parse_structured_json("not json", required=["answer"])

    def test_retrieval_metrics(self):
        results = [[RetrievedChunk(EmbeddingRecord("x", (1,), {"chunk_id": "hit"}), .9)]]
        metrics = evaluate_retrieval(results, [{"hit"}])
        self.assertEqual(metrics.precision_at_k, 1.0)
        self.assertEqual(metrics.recall_at_k, 1.0)

    def test_answer_quality_checks_grounding_and_refusal(self):
        answer = GroundedAnswer("supported", "answered", (Citation("hit", "policy", "s1", "supported", .9),))
        quality = evaluate_answer(answer, {"hit"})
        self.assertTrue(quality.grounded)
        self.assertEqual(quality.citation_accuracy, 1.0)


if __name__ == "__main__":
    unittest.main()

