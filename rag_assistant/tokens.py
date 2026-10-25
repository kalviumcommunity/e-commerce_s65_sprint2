from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UsageEstimate:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost: float


class TokenCounter:
    """Dependency-free conservative token estimator.

    Providers may later replace this with their exact tokenizer. Keeping the
    interface local makes context budgeting deterministic in tests.
    """

    def __init__(self, input_cost_per_1k: float = 0.0, output_cost_per_1k: float = 0.0):
        self.input_cost_per_1k = input_cost_per_1k
        self.output_cost_per_1k = output_cost_per_1k

    @staticmethod
    def count(text: str) -> int:
        if not text:
            return 0
        # Roughly four characters per token, with a minimum for short words.
        return max(1, (len(text) + 3) // 4)

    def estimate(self, prompt: str, completion: str = "") -> UsageEstimate:
        prompt_tokens = self.count(prompt)
        completion_tokens = self.count(completion) if completion else 0
        cost = (prompt_tokens / 1000) * self.input_cost_per_1k
        cost += (completion_tokens / 1000) * self.output_cost_per_1k
        return UsageEstimate(prompt_tokens, completion_tokens,
                             prompt_tokens + completion_tokens, round(cost, 8))

    def trim_to_budget(self, text: str, budget: int) -> str:
        if budget <= 0:
            return ""
        if self.count(text) <= budget:
            return text
        return text[: max(1, budget * 4)]

