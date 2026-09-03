from __future__ import annotations

import json
import threading
import urllib.parse
import urllib.request

from memory.store import SessionStore
from web_app import AgentWebServer, WebState


class FakeRuntime:
    def __init__(self, store: SessionStore) -> None:
        self.store = store

    def run(self, user_id: str, session_id: str, user_input: str) -> str:
        self.store.add_message(user_id, session_id, "user", user_input)
        answer = f"收到：{user_input}"
        self.store.add_message(user_id, session_id, "assistant", answer)
        return answer


def request_json(url: str, *, payload: dict | None = None) -> tuple[int, dict]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def test_web_api_chat_and_session(tmp_path):
    store = SessionStore(tmp_path / "agent.db")
    trace_path = tmp_path / "trace.jsonl"
    trace_path.write_text(
        json.dumps(
            {
                "user_id": "user_a",
                "session_id": "window_1",
                "event": "tool_result",
                "tool_name": "weather",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    state = WebState(
        store=store,
        trace_path=trace_path,
        runtime=FakeRuntime(store),
        runtime_error=None,
    )
    server = AgentWebServer(("127.0.0.1", 0), state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"

    try:
        status, health = request_json(f"{base_url}/api/health")
        assert status == 200
        assert health["ready"] is True

        status, chat = request_json(
            f"{base_url}/api/chat",
            payload={
                "user_id": "user_a",
                "session_id": "window_1",
                "message": "你好",
            },
        )
        assert status == 200
        assert chat["answer"] == "收到：你好"
        assert [message["role"] for message in chat["messages"]] == ["user", "assistant"]

        query = urllib.parse.urlencode({"user_id": "user_a", "session_id": "window_1"})
        status, session = request_json(f"{base_url}/api/session?{query}")
        assert status == 200
        assert session["messages"][-1]["content"] == "收到：你好"
        assert session["traces"][0]["tool_name"] == "weather"

        with urllib.request.urlopen(f"{base_url}/", timeout=5) as response:
            html = response.read().decode("utf-8")
        assert "Agent Runtime" in html
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_web_api_works_when_llm_is_not_configured(tmp_path):
    state = WebState(
        store=SessionStore(tmp_path / "agent.db"),
        trace_path=tmp_path / "trace.jsonl",
        runtime=None,
        runtime_error="缺少 LLM_API_KEY",
    )
    server = AgentWebServer(("127.0.0.1", 0), state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        _, health = request_json(f"http://127.0.0.1:{server.server_port}/api/health")
        assert health["ready"] is False
        assert "LLM_API_KEY" in health["runtime_error"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
