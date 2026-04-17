"""Anthropic Claude LLM adapter — cloud inference via Messages API."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.shared.adapters.llm import LLMResponse


class AnthropicLLMAdapter:
    """LLM adapter for Anthropic's Claude API.

    Requires ANTHROPIC_API_KEY environment variable.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        base_url: str = "https://api.anthropic.com",
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")

    async def generate(
        self, prompt: str, *, max_tokens: int = 2048, temperature: float = 0.7
    ) -> LLMResponse:
        """Call Anthropic Messages API."""
        import httpx

        url = f"{self._base_url}/v1/messages"
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self._model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=2.0)) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")

        usage = data.get("usage", {})
        tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)

        from app.shared.adapters.llm import LLMResponse

        return LLMResponse(
            text=text,
            model=data.get("model", self._model),
            tokens_used=tokens,
        )
