from __future__ import annotations

import ast
import math
import operator
from typing import Any, Callable

from agent.models import ToolExecutionContext, ToolResult
from tools.base import BaseTool


class CalculatorTool(BaseTool):
    name = "calculator"
    description = "安全计算包含数字、括号、加减乘除、整除、取模和有限次幂的数学表达式。"
    parameters_schema = {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "要计算的数学表达式，例如 (17 * 23) + 2",
                "minLength": 1,
                "maxLength": 200,
            }
        },
        "required": ["expression"],
        "additionalProperties": False,
    }

    _binary: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }
    _unary: dict[type[ast.unaryop], Callable[[Any], Any]] = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }

    def _evaluate(self, node: ast.AST) -> int | float:
        if isinstance(node, ast.Expression):
            return self._evaluate(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            if isinstance(node.value, bool):
                raise ValueError("不允许布尔值")
            return node.value
        if isinstance(node, ast.UnaryOp) and type(node.op) in self._unary:
            return self._unary[type(node.op)](self._evaluate(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in self._binary:
            left = self._evaluate(node.left)
            right = self._evaluate(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 10:
                raise ValueError("指数绝对值不能超过 10")
            value = self._binary[type(node.op)](left, right)
            if isinstance(value, complex) or not math.isfinite(float(value)):
                raise ValueError("计算结果不是有限实数")
            if abs(float(value)) > 1e15:
                raise ValueError("计算结果过大")
            return value
        raise ValueError("表达式包含不允许的语法")

    def execute(
        self, arguments: dict[str, Any], context: ToolExecutionContext
    ) -> ToolResult:
        expression = arguments["expression"]
        try:
            tree = ast.parse(expression, mode="eval")
            value = self._evaluate(tree)
            return ToolResult(
                ok=True,
                content=f"{expression} = {value}",
                data={"expression": expression, "result": value},
            )
        except (SyntaxError, ValueError, ZeroDivisionError, OverflowError) as exc:
            return ToolResult(
                ok=False,
                content=f"计算失败: {exc}",
                error_code="CALCULATION_ERROR",
            )
