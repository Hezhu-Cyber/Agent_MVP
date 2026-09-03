from __future__ import annotations

from agent.models import ToolExecutionContext
from memory.store import SessionStore
from tools import CalculatorTool, TodoTool, ToolRegistry
from tools.registry import DuplicateToolError, ToolValidationError


def context(user_id: str = "user_a") -> ToolExecutionContext:
    return ToolExecutionContext(user_id=user_id, session_id="window_1", trace_id="trace")


def test_calculator_computes_expression() -> None:
    result = CalculatorTool().execute({"expression": "17 * 23"}, context())
    assert result.ok is True
    assert result.data["result"] == 391


def test_calculator_rejects_dangerous_expression() -> None:
    result = CalculatorTool().execute(
        {"expression": "__import__('os').system('echo bad')"}, context()
    )
    assert result.ok is False
    assert result.error_code == "CALCULATION_ERROR"


def test_registry_validates_and_rejects_duplicate() -> None:
    registry = ToolRegistry()
    registry.register(CalculatorTool())
    try:
        registry.register(CalculatorTool())
    except DuplicateToolError:
        pass
    else:
        raise AssertionError("重复工具注册应该失败")

    try:
        registry.execute("calculator", {"unexpected": 1}, context())
    except ToolValidationError:
        pass
    else:
        raise AssertionError("非法参数应该失败")


def test_todo_is_scoped_to_user(tmp_path) -> None:
    store = SessionStore(tmp_path / "agent.db")
    tool = TodoTool(store)
    created = tool.execute({"action": "create", "content": "带伞"}, context("user_a"))
    assert created.ok is True
    assert len(store.list_todos("user_a")) == 1
    assert store.list_todos("user_b") == []

    denied = tool.execute(
        {"action": "complete", "todo_id": created.data["id"]}, context("user_b")
    )
    assert denied.ok is False
    assert store.list_todos("user_a")[0]["status"] == "open"
