from __future__ import annotations

from agent.context import ContextBuilder
from memory.store import SessionStore
from tests.fakes import ScriptedLLM
from tracing.logger import TraceLogger


def test_sessions_are_isolated(tmp_path) -> None:
    store = SessionStore(tmp_path / "agent.db")
    store.add_message("user_a", "window_1", "user", "窗口一的秘密")
    store.add_message("user_a", "window_2", "user", "窗口二的周报")
    builder = ContextBuilder(store)

    first = str(builder.build("user_a", "window_1"))
    second = str(builder.build("user_a", "window_2"))
    assert "窗口一的秘密" in first
    assert "窗口二的周报" not in first
    assert "窗口二的周报" in second
    assert "窗口一的秘密" not in second


def test_session_persists_after_reopen(tmp_path) -> None:
    path = tmp_path / "agent.db"
    SessionStore(path).add_message("user_a", "window_1", "user", "记住杭州")
    reopened = SessionStore(path)
    assert reopened.get_messages("user_a", "window_1")[0]["content"] == "记住杭州"


def test_context_compression_keeps_summary_and_recent_messages(tmp_path) -> None:
    store = SessionStore(tmp_path / "agent.db")
    for index in range(21):
        role = "user" if index % 2 == 0 else "assistant"
        store.add_message("user_a", "window_1", role, f"消息-{index}")
    builder = ContextBuilder(store, compression_threshold=20, recent_messages=10)
    llm = ScriptedLLM()
    trace = TraceLogger(tmp_path / "trace.jsonl", console=False)

    assert builder.maybe_compress("user_a", "window_1", llm, trace, "trace") is True
    messages = builder.build("user_a", "window_1")
    rendered = str(messages)
    assert llm.summary_calls == 1
    assert "较早历史摘要" in rendered
    assert "消息-20" in rendered
    assert "消息-0" not in rendered
