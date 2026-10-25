from __future__ import annotations

from dataclasses import dataclass, field

from .tokens import TokenCounter


@dataclass(frozen=True)
class Message:
    role: str
    content: str


@dataclass
class Conversation:
    """In-memory conversation with a deterministic, token-aware history window."""

    token_counter: TokenCounter
    context_window: int
    reserved_output_tokens: int = 512
    messages: list[Message] = field(default_factory=list)

    def add(self, role: str, content: str) -> None:
        if role not in {"system", "user", "assistant"}:
            raise ValueError("role must be system, user, or assistant")
        if not content.strip():
            raise ValueError("message content cannot be empty")
        self.messages.append(Message(role, content.strip()))

    def prompt_messages(self, system_prompt: str | None = None) -> list[dict[str, str]]:
        budget = max(1, self.context_window - self.reserved_output_tokens)
        selected: list[Message] = []
        used = self.token_counter.count(system_prompt or "")
        if system_prompt:
            selected.append(Message("system", system_prompt))
        for message in reversed(self.messages):
            cost = self.token_counter.count(message.content)
            if selected and used + cost > budget:
                break
            selected.append(message)
            used += cost
        if system_prompt:
            history = selected[1:]
            return [{"role": "system", "content": system_prompt}] + [m.__dict__ for m in reversed(history)]
        return [m.__dict__ for m in reversed(selected)]

