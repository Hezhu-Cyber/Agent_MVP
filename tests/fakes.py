from __future__ import annotations

from typing import Any

from llm.base import LLMClient


class ScriptedLLM(LLMClient):
    def __init__(self, responses: list[dict[str, Any]] | None = None) -> None:
        self.responses = list(responses or [])
        self.calls: list[dict[str, Any]] = []
        self.summary_calls = 0

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        self.calls.append({"messages": messages, "tools": tools})
        if not self.responses:
            raise AssertionError("ScriptedLLM 没有剩余响应")
        return self.responses.pop(0)

    def summarize(self, previous_summary: str, messages: list[dict[str, Any]]) -> str:
        self.summary_calls += 1
        return (
            "confirmed_facts:\n- 用户持续进行测试\n"
            "user_preferences:\n- 无\n"
            "completed_actions:\n- 已压缩早期对话\n"
            "open_tasks:\n- 继续对话\n"
            "important_references:\n- 无"
        )


def tool_call(call_id: str, name: str, arguments: str) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": arguments},
            }
        ],
    }


def final(content: str) -> dict[str, Any]:
    return {"role": "assistant", "content": content}
