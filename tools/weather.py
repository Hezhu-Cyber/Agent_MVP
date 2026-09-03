from __future__ import annotations

from typing import Any

from agent.models import ToolExecutionContext, ToolResult
from tools.base import BaseTool


class WeatherTool(BaseTool):
    name = "weather"
    description = "查询固定的模拟天气数据，用于演示多步工具调用，不代表实时天气。"
    parameters_schema = {
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "城市名称", "minLength": 1},
            "date": {
                "type": "string",
                "description": "日期描述，例如 today、tomorrow 或 2026-09-03",
                "minLength": 1,
            },
        },
        "required": ["city", "date"],
        "additionalProperties": False,
    }
    _weather = {
        "上海": {"condition": "小雨", "temperature": "22°C", "rain": True},
        "北京": {"condition": "晴", "temperature": "25°C", "rain": False},
        "杭州": {"condition": "多云", "temperature": "24°C", "rain": False},
        "深圳": {"condition": "阵雨", "temperature": "29°C", "rain": True},
    }

    def execute(
        self, arguments: dict[str, Any], context: ToolExecutionContext
    ) -> ToolResult:
        city = arguments["city"].strip()
        date = arguments["date"].strip()
        data = self._weather.get(
            city, {"condition": "晴间多云", "temperature": "23°C", "rain": False}
        )
        payload = {"city": city, "date": date, **data, "mock": True}
        return ToolResult(
            ok=True,
            content=(
                f"模拟天气：{city} {date} {data['condition']}，"
                f"{data['temperature']}，是否有雨：{'是' if data['rain'] else '否'}。"
            ),
            data=payload,
        )
