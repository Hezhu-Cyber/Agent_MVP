from __future__ import annotations

import json

from llm.client import OpenAIChatClient


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_openai_client_sends_tool_schema(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["authorization"] = request.headers["Authorization"]
        return FakeResponse(
            {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = OpenAIChatClient(
        api_key="test-key",
        model="test-model",
        base_url="https://example.test/v1/",
        timeout_seconds=3,
    )
    tools = [
        {
            "type": "function",
            "function": {
                "name": "calculator",
                "description": "calc",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]
    result = client.complete([{"role": "user", "content": "hello"}], tools)

    assert result["content"] == "ok"
    assert captured["url"] == "https://example.test/v1/chat/completions"
    assert captured["authorization"] == "Bearer test-key"
    assert captured["body"]["tools"] == tools
    assert captured["body"]["parallel_tool_calls"] is False
