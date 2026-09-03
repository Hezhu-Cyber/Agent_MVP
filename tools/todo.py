from __future__ import annotations

from typing import Any

from agent.models import ToolExecutionContext, ToolResult
from memory.store import SessionStore
from tools.base import BaseTool


class TodoTool(BaseTool):
    name = "todo"
    description = "创建、查询或完成当前用户的待办。用户身份由 Runtime 注入。"
    parameters_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "要执行的待办操作",
                "enum": ["create", "list", "complete"],
            },
            "content": {
                "type": "string",
                "description": "create 时的待办内容",
                "minLength": 1,
                "maxLength": 500,
            },
            "todo_id": {
                "type": "integer",
                "description": "complete 时的待办 ID",
                "minimum": 1,
            },
            "status": {
                "type": "string",
                "description": "list 时的状态过滤",
                "enum": ["all", "open", "completed"],
            },
        },
        "required": ["action"],
        "additionalProperties": False,
    }

    def __init__(self, store: SessionStore) -> None:
        self.store = store

    def execute(
        self, arguments: dict[str, Any], context: ToolExecutionContext
    ) -> ToolResult:
        action = arguments["action"]
        if action == "create":
            content = str(arguments.get("content", "")).strip()
            if not content:
                return ToolResult(False, "create 操作缺少 content", error_code="INVALID_TODO")
            todo = self.store.create_todo(context.user_id, context.session_id, content)
            return ToolResult(
                True,
                f"已创建待办 #{todo['id']}: {todo['content']}",
                data=todo,
            )

        if action == "list":
            status = arguments.get("status", "all")
            todos = self.store.list_todos(context.user_id, status)
            if not todos:
                return ToolResult(True, "当前没有符合条件的待办。", data=[])
            lines = [
                f"#{item['id']} [{item['status']}] {item['content']}"
                for item in todos
            ]
            return ToolResult(True, "待办列表：\n" + "\n".join(lines), data=todos)

        todo_id = arguments.get("todo_id")
        if not isinstance(todo_id, int):
            return ToolResult(False, "complete 操作缺少 todo_id", error_code="INVALID_TODO")
        todo = self.store.complete_todo(context.user_id, todo_id)
        if todo is None:
            return ToolResult(
                False,
                f"找不到属于当前用户的待办 #{todo_id}",
                error_code="TODO_NOT_FOUND",
            )
        return ToolResult(True, f"已完成待办 #{todo_id}: {todo['content']}", data=todo)
