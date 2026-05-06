from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Final

from ..config.settings import Settings
from .http import LLMHTTPError, post_json


class LLMConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class LLMResult:
    provider: str
    model: str
    text: str
    raw: dict[str, Any]


class LLMClient:
    provider: str

    def generate_text(self, *, model: str, system: str, user: str, temperature: float, max_tokens: int) -> LLMResult:
        raise NotImplementedError

    def generate_json(
        self,
        *,
        model: str,
        system: str,
        user: str,
        temperature: float,
        max_tokens: int,
    ) -> tuple[LLMResult, dict[str, Any]]:
        result = self.generate_text(
            model=model,
            system=system,
            user=user,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        try:
            parsed = json.loads(result.text)
        except json.JSONDecodeError as exc:
            raise LLMHTTPError(f"LLM returned invalid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise LLMHTTPError("LLM returned JSON but not an object.")
        return result, parsed


class AnthropicClient(LLMClient):
    provider = "anthropic"
    _API_URL: Final[str] = "https://api.anthropic.com/v1/messages"
    _VERSION: Final[str] = "2023-06-01"

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise LLMConfigurationError("Missing ANTHROPIC_API_KEY.")
        self.api_key = api_key

    def generate_text(self, *, model: str, system: str, user: str, temperature: float, max_tokens: int) -> LLMResult:
        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": int(max_tokens),
            "temperature": float(temperature),
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self._VERSION,
        }
        response = post_json(self._API_URL, payload, headers=headers, timeout_seconds=45.0)
        content = response.body.get("content", [])
        if isinstance(content, list):
            text = "".join(block.get("text", "") for block in content if isinstance(block, dict))
        else:
            text = str(content)
        return LLMResult(provider=self.provider, model=model, text=text.strip(), raw=response.body)


class GeminiClient(LLMClient):
    provider = "gemini"
    _API_ROOT: Final[str] = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise LLMConfigurationError("Missing GOOGLE_API_KEY.")
        self.api_key = api_key

    def generate_text(self, *, model: str, system: str, user: str, temperature: float, max_tokens: int) -> LLMResult:
        url = f"{self._API_ROOT}/{model}:generateContent?key={self.api_key}"
        prompt = f"{system}\n\n{user}".strip()
        payload: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": float(temperature),
                "maxOutputTokens": int(max_tokens),
            },
        }
        response = post_json(url, payload, headers={}, timeout_seconds=45.0)
        candidates = response.body.get("candidates") or []
        parts: list[dict[str, Any]] = []
        if candidates and isinstance(candidates, list):
            content = candidates[0].get("content", {}) if isinstance(candidates[0], dict) else {}
            parts = content.get("parts", []) if isinstance(content, dict) else []
        text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
        return LLMResult(provider=self.provider, model=model, text=text.strip(), raw=response.body)


def client_from_settings(settings: Settings, provider: str) -> LLMClient:
    normalized = provider.lower().strip()
    if normalized in {"anthropic", "claude"}:
        return AnthropicClient(settings.anthropic_api_key)
    if normalized in {"gemini", "google"}:
        return GeminiClient(settings.google_api_key)
    raise LLMConfigurationError(f"Unsupported LLM provider: {provider}")

