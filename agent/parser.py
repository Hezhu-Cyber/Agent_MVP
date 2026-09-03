from __future__ import annotations

import json
from typing import Any

from agent.models import Decision, ToolCall


class LLMOutputError(ValueError):
    pass


def _text_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(parts).strip()
    return ""


class OutputParser:
    def parse(self, message: dict[str, Any]) -> Decision:
        if not isinstance(message, dict):
            raise LLMOutputError("模型消息必须是对象")

        tool_calls = message.get("tool_calls") or []
        if tool_calls:
            if not isinstance(tool_calls, list) or not isinstance(tool_calls[0], dict):
                raise LLMOutputError("tool_calls 格式错误")
            raw_call = tool_calls[0]
            function = raw_call.get("function") or {}
            name = function.get("name")
            call_id = raw_call.get("id")
            raw_arguments = function.get("arguments", "{}")
            if not isinstance(name, str) or not name:
                raise LLMOutputError("工具调用缺少名称")
            if not isinstance(call_id, str) or not call_id:
                raise LLMOutputError("工具调用缺少 id")
            try:
                arguments = (
                    raw_arguments
                    if isinstance(raw_arguments, dict)
                    else json.loads(raw_arguments or "{}")
                )
            except json.JSONDecodeError as exc:
                raise LLMOutputError(f"工具参数不是合法 JSON: {exc}") from exc
            if not isinstance(arguments, dict):
                raise LLMOutputError("工具参数必须是 JSON 对象")
            summary = _text_content(message.get("content")) or f"调用工具 {name}"
            return Decision(
                type="tool_call",
                decision_summary=summary,
                tool_call=ToolCall(call_id, name, arguments),
                raw_message=message,
            )

        content = _text_content(message.get("content"))
        if not content:
            raise LLMOutputError("模型未返回答案或工具调用")

        # Also accept the explicit structured protocol from the execution document.
        candidate = content.strip()
        if candidate.startswith("```"):
            lines = candidate.splitlines()
            candidate = "\n".join(lines[1:-1]).strip() if len(lines) >= 3 else candidate
        if candidate.startswith("{"):
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                payload = None
            if isinstance(payload, dict) and payload.get("type") == "final":
                answer = payload.get("answer")
                if not isinstance(answer, str) or not answer.strip():
                    raise LLMOutputError("final 输出缺少 answer")
                return Decision(
                    type="final",
                    decision_summary=str(payload.get("decision_summary", "直接回答")),
                    answer=answer.strip(),
                    raw_message=message,
                )
            if isinstance(payload, dict) and payload.get("type") == "tool_call":
                raw = payload.get("tool_call") or {}
                try:
                    call = ToolCall(
                        id=str(raw.get("id") or "structured_call"),
                        name=str(raw["name"]),
                        arguments=dict(raw.get("arguments") or {}),
                    )
                except (KeyError, TypeError, ValueError) as exc:
                    raise LLMOutputError("结构化 tool_call 格式错误") from exc
                return Decision(
                    type="tool_call",
                    decision_summary=str(payload.get("decision_summary", f"调用工具 {call.name}")),
                    tool_call=call,
                    raw_message=message,
                )

        return Decision(
            type="final",
            decision_summary="直接回答",
            answer=content,
            raw_message=message,
        )
