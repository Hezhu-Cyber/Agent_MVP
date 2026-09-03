from __future__ import annotations

from typing import Any

from agent.models import ToolExecutionContext, ToolResult
from tools.base import BaseTool


class ToolError(Exception):
    """Base error for tool registration and execution."""


class DuplicateToolError(ToolError):
    pass


class ToolNotFoundError(ToolError):
    pass


class ToolValidationError(ToolError):
    pass


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    return True


def validate_arguments(arguments: Any, schema: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise ToolValidationError("工具参数必须是 JSON 对象")

    properties = schema.get("properties", {})
    required = schema.get("required", [])
    missing = [name for name in required if name not in arguments]
    if missing:
        raise ToolValidationError(f"缺少必填参数: {', '.join(missing)}")

    if schema.get("additionalProperties") is False:
        extras = sorted(set(arguments) - set(properties))
        if extras:
            raise ToolValidationError(f"存在未定义参数: {', '.join(extras)}")

    for name, value in arguments.items():
        rule = properties.get(name)
        if not rule:
            continue
        expected = rule.get("type")
        if expected and not _matches_type(value, expected):
            raise ToolValidationError(
                f"参数 {name} 类型错误，期望 {expected}，实际 {type(value).__name__}"
            )
        if "enum" in rule and value not in rule["enum"]:
            choices = ", ".join(map(str, rule["enum"]))
            raise ToolValidationError(f"参数 {name} 必须是以下之一: {choices}")
        if isinstance(value, str):
            if "minLength" in rule and len(value) < rule["minLength"]:
                raise ToolValidationError(f"参数 {name} 太短")
            if "maxLength" in rule and len(value) > rule["maxLength"]:
                raise ToolValidationError(f"参数 {name} 太长")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in rule and value < rule["minimum"]:
                raise ToolValidationError(f"参数 {name} 小于最小值 {rule['minimum']}")
            if "maximum" in rule and value > rule["maximum"]:
                raise ToolValidationError(f"参数 {name} 大于最大值 {rule['maximum']}")
    return arguments


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        if tool.name in self._tools:
            raise DuplicateToolError(f"工具已注册: {tool.name}")
        self._tools[tool.name] = tool

    def names(self) -> list[str]:
        return sorted(self._tools)

    def schemas(self) -> list[dict[str, Any]]:
        return [self._tools[name].api_schema() for name in self.names()]

    def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            available = ", ".join(self.names())
            raise ToolNotFoundError(f"未知工具 {name}；可用工具: {available}")
        validated = validate_arguments(arguments, tool.parameters_schema)
        return tool.execute(validated, context)
