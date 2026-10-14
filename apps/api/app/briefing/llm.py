import json
from typing import Protocol

import httpx

from app.core.config import settings


class LLMError(Exception):
    """The model could not be reached or returned something unusable."""


class LLMClient(Protocol):
    model_name: str

    async def generate_json(self, system: str, prompt: str, schema: dict) -> dict: ...


class OllamaClient:
    def __init__(self, base_url: str, model: str, timeout: float) -> None:
        self.model_name = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def generate_json(self, system: str, prompt: str, schema: dict) -> dict:
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            # Ollama constrains decoding to this JSON schema.
            "format": schema,
            "stream": False,
            # Loading the model into VRAM costs minutes on a cold start; keep it warm.
            "keep_alive": "30m",
            "options": {"temperature": 0.2, "num_ctx": 8192},
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(f"{self._base_url}/api/chat", json=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMError(f"Ollama request failed: {exc!r}") from exc
        content = response.json().get("message", {}).get("content", "")
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMError("Model returned invalid JSON") from exc
        if not isinstance(parsed, dict):
            raise LLMError("Model returned JSON that is not an object")
        return parsed


def get_llm_client() -> LLMClient:
    return OllamaClient(settings.ollama_base_url, settings.llm_model, settings.llm_timeout_seconds)
