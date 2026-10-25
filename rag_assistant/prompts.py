from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class PromptTemplate:
    name: str
    system: str
    version: str = "v1"

    def render(self, **values: str) -> str:
        return self.system.format(**values)


GROUNDED_ANSWER = PromptTemplate(
    "grounded-answer",
    "You are a policy assistant. Use only the evidence below. Cite source chunk IDs. "
    "If evidence is insufficient, refuse safely. Return JSON with answer, status, and citations.\n"
    "Evidence:\n{context}\nQuestion: {question}",
)


def parse_structured_json(text: str, *, required: Sequence[str]) -> Mapping[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("expected valid JSON output") from exc
    if not isinstance(value, dict) or any(key not in value for key in required):
        raise ValueError("structured output is missing required fields")
    return value

