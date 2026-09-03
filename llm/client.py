from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from llm.base import LLMClient, LLMError


class OpenAIChatClient(LLMClient):
    """Small direct HTTP client for an OpenAI-compatible Chat Completions API."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 60,
        max_retries: int = 2,
    ) -> None:
        if not api_key or api_key == "replace-me":
            raise ValueError("请通过 LLM_API_KEY 配置真实 API Key")
        if not model or model.startswith("replace-"):
            raise ValueError("请通过 LLM_MODEL 配置支持工具调用的模型")
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"model": self.model, "messages": messages}
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
            payload["parallel_tool_calls"] = False
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

        for attempt in range(self.max_retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    data = json.loads(response.read().decode("utf-8"))
                choices = data.get("choices") or []
                if not choices or not isinstance(choices[0].get("message"), dict):
                    raise LLMError("LLM 响应缺少 choices[0].message")
                return choices[0]["message"]
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")[:1000]
                retryable = exc.code == 429 or 500 <= exc.code < 600
                if retryable and attempt < self.max_retries:
                    time.sleep(0.5 * (2**attempt))
                    continue
                raise LLMError(f"LLM HTTP {exc.code}: {detail}") from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempt < self.max_retries:
                    time.sleep(0.5 * (2**attempt))
                    continue
                raise LLMError(f"LLM 网络请求失败: {exc}") from exc
            except json.JSONDecodeError as exc:
                raise LLMError("LLM 返回的内容不是合法 JSON") from exc
        raise LLMError("LLM 请求失败")
