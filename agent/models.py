from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class Decision:
    type: Literal["final", "tool_call"]
    decision_summary: str
    answer: str | None = None
    tool_call: ToolCall | None = None
    raw_message: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolExecutionContext:
    user_id: str
    session_id: str
    trace_id: str


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    content: str
    data: Any = None
    error_code: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"ok": self.ok, "content": self.content}
        if self.data is not None:
            payload["data"] = self.data
        if self.error_code:
            payload["error_code"] = self.error_code
        return payload
