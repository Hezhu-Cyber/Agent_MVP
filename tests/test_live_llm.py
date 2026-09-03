from __future__ import annotations

import os

import pytest

from app import build_runtime, load_dotenv
from memory.store import SessionStore


def require_live_config() -> None:
    load_dotenv()
    if os.getenv("RUN_LIVE_LLM") != "1":
        pytest.skip("设置 RUN_LIVE_LLM=1 后才执行真实 LLM 测试")
    if not os.getenv("LLM_API_KEY") or not os.getenv("LLM_MODEL"):
        pytest.skip("缺少 LLM_API_KEY 或 LLM_MODEL")


@pytest.mark.live_llm
def test_real_llm_calculator(tmp_path) -> None:
    require_live_config()
    db_path = tmp_path / "live-calculator.db"
    runtime = build_runtime(
        db_path=str(db_path),
        trace_path=str(tmp_path / "live-calculator.jsonl"),
    )
    answer = runtime.run("live_user", "calculator", "请使用工具计算 17 * 23")
    assert "391" in answer
    assert any(
        item["role"] == "tool" and item["tool_name"] == "calculator"
        for item in SessionStore(db_path).get_messages("live_user", "calculator")
    )


@pytest.mark.live_llm
def test_real_llm_search(tmp_path) -> None:
    require_live_config()
    db_path = tmp_path / "live-search.db"
    runtime = build_runtime(
        db_path=str(db_path),
        trace_path=str(tmp_path / "live-search.jsonl"),
    )
    runtime.run("live_user", "search", "请使用 search 工具搜索 Agent Runtime 并总结")
    assert any(
        item["role"] == "tool" and item["tool_name"] == "search"
        for item in SessionStore(db_path).get_messages("live_user", "search")
    )


@pytest.mark.live_llm
def test_real_llm_weather_then_todo(tmp_path) -> None:
    require_live_config()
    db_path = tmp_path / "live-weather.db"
    runtime = build_runtime(
        db_path=str(db_path),
        trace_path=str(tmp_path / "live-weather.jsonl"),
    )
    runtime.run(
        "live_user",
        "weather",
        "请查明天上海天气；如果有雨，创建一个明天出门带伞的待办。",
    )
    store = SessionStore(db_path)
    tool_names = [
        item["tool_name"]
        for item in store.get_messages("live_user", "weather")
        if item["role"] == "tool"
    ]
    assert tool_names[:2] == ["weather", "todo"]
    assert store.list_todos("live_user")
