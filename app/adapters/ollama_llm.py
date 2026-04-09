"""Ollama LLM adapter — local inference via Ollama HTTP API."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.shared.adapters.llm import LLMResponse


class OllamaLLMAdapter:
    """LLM adapter for Ollama (local inference server).

    Supports Llama, Mistral, Phi, Gemma, and any model pulled into Ollama.
    API docs: https://github.com/ollama/ollama/blob/main/docs/api.md
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.1:8b",
        timeout: int = 120,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout

    async def generate(
        self, prompt: str, *, max_tokens: int = 2048, temperature: float = 0.7
    ) -> LLMResponse:
        """Call Ollama's /api/generate endpoint."""
        import httpx

        url = f"{self._base_url}/api/generate"
        payload = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        # Ollama returns: model, response, eval_count, prompt_eval_count
        from app.shared.adapters.llm import LLMResponse

        return LLMResponse(
            text=data.get("response", ""),
            model=data.get("model", self._model),
            tokens_used=data.get("eval_count", 0) + data.get("prompt_eval_count", 0),
        )
