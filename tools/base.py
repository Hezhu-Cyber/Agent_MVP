from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from agent.models import ToolExecutionContext, ToolResult


class BaseTool(ABC):
    name: str
    description: str
    parameters_schema: dict[str, Any]

    def api_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }

    @abstractmethod
    def execute(
        self, arguments: dict[str, Any], context: ToolExecutionContext
    ) -> ToolResult:
        raise NotImplementedError
