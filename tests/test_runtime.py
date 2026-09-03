from __future__ import annotations

from agent.context import ContextBuilder
from agent.runtime import AgentRuntime
from memory.store import SessionStore
from tests.fakes import ScriptedLLM, final, tool_call
from tools import CalculatorTool, SearchTool, TodoTool, ToolRegistry, WeatherTool
from tracing.logger import TraceLogger


def make_runtime(tmp_path, responses):
    store = SessionStore(tmp_path / "agent.db")
    registry = ToolRegistry()
    registry.register(CalculatorTool())
    registry.register(SearchTool())
    registry.register(TodoTool(store))
    registry.register(WeatherTool())
    llm = ScriptedLLM(responses)
    runtime = AgentRuntime(
        llm=llm,
        registry=registry,
        store=store,
        context_builder=ContextBuilder(store),
        trace=TraceLogger(tmp_path / "traces.jsonl", console=False),
    )
    return runtime, store, llm


def test_direct_answer(tmp_path) -> None:
    runtime, store, _ = make_runtime(tmp_path, [final("你好，我可以帮你。")])
    answer = runtime.run("user_a", "window_1", "你好")
    assert answer == "你好，我可以帮你。"
    assert [m["role"] for m in store.get_messages("user_a", "window_1")] == [
        "user",
        "assistant",
    ]


def test_calculator_loop(tmp_path) -> None:
    runtime, store, llm = make_runtime(
        tmp_path,
        [
            tool_call("calc_1", "calculator", '{"expression":"17*23"}'),
            final("17 × 23 = 391。"),
        ],
    )
    answer = runtime.run("user_a", "window_1", "计算 17 乘 23")
    assert "391" in answer
    roles = [m["role"] for m in store.get_messages("user_a", "window_1")]
    assert roles == ["user", "assistant", "tool", "assistant"]
    second_context = llm.calls[1]["messages"]
    assert any(message["role"] == "tool" and "391" in message["content"] for message in second_context)


def test_weather_then_todo(tmp_path) -> None:
    runtime, store, _ = make_runtime(
        tmp_path,
        [
            tool_call("weather_1", "weather", '{"city":"上海","date":"tomorrow"}'),
            tool_call("todo_1", "todo", '{"action":"create","content":"明天出门带伞"}'),
            final("明天上海有雨，已创建带伞待办。"),
        ],
    )
    answer = runtime.run("user_a", "window_1", "查明天上海天气，下雨就记得提醒我带伞")
    assert "已创建" in answer
    todos = store.list_todos("user_a")
    assert len(todos) == 1
    assert todos[0]["content"] == "明天出门带伞"


def test_duplicate_tool_call_stops_loop(tmp_path) -> None:
    repeated = '{"expression":"1+1"}'
    runtime, _, _ = make_runtime(
        tmp_path,
        [
            tool_call("first", "calculator", repeated),
            tool_call("second", "calculator", repeated),
        ],
    )
    answer = runtime.run("user_a", "window_1", "重复调用")
    assert "重复工具调用" in answer


def test_tool_validation_error_is_returned_to_llm(tmp_path) -> None:
    runtime, _, llm = make_runtime(
        tmp_path,
        [
            tool_call("bad", "calculator", '{"wrong":"2+2"}'),
            final("工具参数有误，未执行计算。"),
        ],
    )
    answer = runtime.run("user_a", "window_1", "计算")
    assert "参数有误" in answer
    second_context = str(llm.calls[1]["messages"])
    assert "ToolValidationError" in second_context


def test_invalid_model_output_is_corrected(tmp_path) -> None:
    runtime, _, llm = make_runtime(
        tmp_path,
        [
            {"role": "assistant", "content": None},
            final("纠正后回答。"),
        ],
    )
    answer = runtime.run("user_a", "window_1", "请回答")
    assert answer == "纠正后回答。"
    retry_context = str(llm.calls[1]["messages"])
    assert "无法解析的空输出" in retry_context
