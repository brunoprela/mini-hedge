"""LLMAdapter protocol and LLMResponse value object."""

from __future__ import annotations

from typing import Protocol


class LLMResponse:
    """Raw response from an LLM backend."""

    __slots__ = ("text", "model", "tokens_used")

    def __init__(self, *, text: str, model: str, tokens_used: int) -> None:
        self.text = text
        self.model = model
        self.tokens_used = tokens_used


class LLMAdapter(Protocol):
    """Vendor-agnostic LLM inference interface.

    Implementations: ollama (local), anthropic (Claude API), mock.
    """

    async def generate(
        self, prompt: str, *, max_tokens: int = 2048, temperature: float = 0.7
    ) -> LLMResponse: ...
