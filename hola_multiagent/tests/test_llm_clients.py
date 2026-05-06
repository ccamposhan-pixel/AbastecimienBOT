from __future__ import annotations

from hola_multiagent.llm.http import HTTPResponse
from hola_multiagent.llm.providers import AnthropicClient, GeminiClient


def test_anthropic_client_extracts_text(monkeypatch):
    def fake_post_json(url, payload, headers=None, timeout_seconds=30.0):
        return HTTPResponse(
            status=200,
            body={"content": [{"type": "text", "text": "{\"ok\": true}"}]},
        )

    monkeypatch.setattr("hola_multiagent.llm.providers.post_json", fake_post_json)
    client = AnthropicClient(api_key="test")
    result = client.generate_text(model="claude-test", system="sys", user="hi", temperature=0, max_tokens=10)
    assert result.text == "{\"ok\": true}"


def test_gemini_client_extracts_text(monkeypatch):
    def fake_post_json(url, payload, headers=None, timeout_seconds=30.0):
        return HTTPResponse(
            status=200,
            body={"candidates": [{"content": {"parts": [{"text": "respuesta"}]}}]},
        )

    monkeypatch.setattr("hola_multiagent.llm.providers.post_json", fake_post_json)
    client = GeminiClient(api_key="test")
    result = client.generate_text(model="gemini-test", system="sys", user="hi", temperature=0, max_tokens=10)
    assert result.text == "respuesta"

