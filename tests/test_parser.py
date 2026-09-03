from __future__ import annotations

import pytest

from agent.parser import LLMOutputError, OutputParser
from tests.fakes import final, tool_call


def test_parse_native_tool_call() -> None:
    decision = OutputParser().parse(tool_call("c1", "calculator", '{"expression":"2+2"}'))
    assert decision.type == "tool_call"
    assert decision.tool_call is not None
    assert decision.tool_call.name == "calculator"
    assert decision.tool_call.arguments == {"expression": "2+2"}


def test_parse_plain_final() -> None:
    decision = OutputParser().parse(final("你好！"))
    assert decision.type == "final"
    assert decision.answer == "你好！"


def test_parse_structured_final() -> None:
    decision = OutputParser().parse(
        final('{"type":"final","decision_summary":"完成","answer":"结果"}')
    )
    assert decision.answer == "结果"
    assert decision.decision_summary == "完成"


def test_reject_empty_message() -> None:
    with pytest.raises(LLMOutputError):
        OutputParser().parse({"role": "assistant", "content": None})
