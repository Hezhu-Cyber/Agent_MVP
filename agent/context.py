from __future__ import annotations

import json
from typing import Any

from agent.prompts import SYSTEM_PROMPT
from llm.base import LLMClient
from memory.store import SessionStore
from tracing.logger import TraceLogger


class ContextBuilder:
    def __init__(
        self,
        store: SessionStore,
        *,
        compression_threshold: int = 20,
        recent_messages: int = 10,
    ) -> None:
        self.store = store
        self.compression_threshold = compression_threshold
        self.recent_messages = recent_messages

    @staticmethod
    def _to_api_message(row: dict[str, Any]) -> dict[str, Any]:
        role = row["role"]
        if role == "assistant" and row.get("tool_call_id"):
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": row["tool_call_id"],
                        "type": "function",
                        "function": {
                            "name": row["tool_name"],
                            "arguments": row["content"],
                        },
                    }
                ],
            }
        if role == "tool":
            return {
                "role": "tool",
                "tool_call_id": row["tool_call_id"],
                "name": row["tool_name"],
                "content": row["content"],
            }
        return {"role": role, "content": row["content"]}

    def maybe_compress(
        self,
        user_id: str,
        session_id: str,
        llm: LLMClient,
        trace: TraceLogger,
        trace_id: str,
    ) -> bool:
        session = self.store.get_or_create_session(user_id, session_id)
        pending = self.store.get_messages(
            user_id, session_id, after_id=int(session["summarized_through"])
        )
        if len(pending) <= self.compression_threshold:
            return False
        older = pending[: -self.recent_messages]
        if not older:
            return False
        api_messages = [self._to_api_message(row) for row in older]
        try:
            summary = llm.summarize(session["summary"], api_messages)
            through = int(older[-1]["id"])
            self.store.update_summary(user_id, session_id, summary, through)
            trace.event(
                "context_compressed",
                trace_id=trace_id,
                step=0,
                summarized_messages=len(older),
                summarized_through=through,
            )
            return True
        except Exception as exc:
            trace.event(
                "context_compression_failed",
                trace_id=trace_id,
                step=0,
                error=str(exc),
            )
            return False

    def build(self, user_id: str, session_id: str) -> list[dict[str, Any]]:
        session = self.store.get_or_create_session(user_id, session_id)
        messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        summary = str(session.get("summary") or "").strip()
        if summary:
            messages.append(
                {
                    "role": "system",
                    "content": "当前 Session 的较早历史摘要：\n" + summary,
                }
            )
        rows = self.store.get_messages(
            user_id,
            session_id,
            after_id=int(session.get("summarized_through") or 0),
            limit=max(self.compression_threshold, self.recent_messages),
        )
        messages.extend(self._to_api_message(row) for row in rows)
        return messages
