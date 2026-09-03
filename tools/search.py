from __future__ import annotations

from typing import Any

from agent.models import ToolExecutionContext, ToolResult
from tools.base import BaseTool


class SearchTool(BaseTool):
    name = "search"
    description = "从本地模拟搜索库中查询资料。结果用于演示工具调用，不代表实时互联网信息。"
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词",
                "minLength": 1,
                "maxLength": 200,
            },
            "limit": {
                "type": "integer",
                "description": "返回结果数量，默认 3",
                "minimum": 1,
                "maximum": 5,
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    }

    _documents = [
        {
            "title": "Agent Runtime 基础",
            "snippet": "Agent Runtime 通过模型决策、工具执行和结果反馈形成循环。",
            "url": "mock://agent-runtime-basics",
            "keywords": "agent runtime loop 工具 tool",
        },
        {
            "title": "工具调用与 JSON Schema",
            "snippet": "工具名称、描述与参数 Schema 能帮助模型选择并正确调用工具。",
            "url": "mock://tool-schema",
            "keywords": "tool schema json 参数 工具",
        },
        {
            "title": "Session 与上下文隔离",
            "snippet": "使用 user_id 与 session_id 组合键可以避免不同窗口的历史串话。",
            "url": "mock://session-context",
            "keywords": "session context memory 上下文 窗口",
        },
        {
            "title": "Python 项目测试",
            "snippet": "单元测试验证组件，脚本化模型可稳定测试多步 Agent Loop。",
            "url": "mock://python-testing",
            "keywords": "python pytest test 测试 mock",
        },
        {
            "title": "上下文压缩",
            "snippet": "保留摘要和最近消息，是长对话中成本较低的基础压缩方式。",
            "url": "mock://context-compression",
            "keywords": "context compression summary 上下文 摘要",
        },
    ]

    def execute(
        self, arguments: dict[str, Any], context: ToolExecutionContext
    ) -> ToolResult:
        query = arguments["query"].strip()
        limit = arguments.get("limit", 3)
        terms = [term.lower() for term in query.split() if term.strip()]

        def score(document: dict[str, str]) -> int:
            haystack = " ".join(document.values()).lower()
            return sum(1 for term in terms if term in haystack)

        ranked = sorted(self._documents, key=score, reverse=True)
        selected = ranked[:limit]
        content = "\n".join(
            f"{index}. {item['title']} - {item['snippet']} ({item['url']})"
            for index, item in enumerate(selected, start=1)
        )
        return ToolResult(
            ok=True,
            content=f"模拟搜索结果（查询：{query}）：\n{content}",
            data=[{k: v for k, v in item.items() if k != "keywords"} for item in selected],
        )
