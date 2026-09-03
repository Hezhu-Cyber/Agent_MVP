from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMError(RuntimeError):
    pass


class LLMClient(ABC):
    @abstractmethod
    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Return one assistant message in Chat Completions-compatible form."""
        raise NotImplementedError

    def summarize(self, previous_summary: str, messages: list[dict[str, Any]]) -> str:
        text = "\n".join(
            f"[{message.get('role')}] {message.get('content', '')}" for message in messages
        )
        prompt = (
            "请压缩下面的会话历史。只保留对后续对话有用的信息，并严格使用以下标题：\n"
            "confirmed_facts:\nuser_preferences:\ncompleted_actions:\n"
            "open_tasks:\nimportant_references:\n\n"
            f"已有摘要：\n{previous_summary or '(无)'}\n\n新增历史：\n{text}"
        )
        response = self.complete(
            [
                {
                    "role": "system",
                    "content": "你负责生成简洁、忠实、无推测的会话摘要。",
                },
                {"role": "user", "content": prompt},
            ]
        )
        content = response.get("content")
        if not isinstance(content, str) or not content.strip():
            raise LLMError("摘要模型返回空内容")
        return content.strip()
