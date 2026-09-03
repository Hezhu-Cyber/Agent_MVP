from __future__ import annotations

import json
import time
import uuid
from typing import Any

from agent.context import ContextBuilder
from agent.models import Decision, ToolExecutionContext, ToolResult
from agent.parser import LLMOutputError, OutputParser
from agent.prompts import FORMAT_CORRECTION_PROMPT
from llm.base import LLMClient, LLMError
from memory.store import SessionStore
from tools.registry import ToolError, ToolRegistry
from tracing.logger import TraceLogger


class AgentRuntime:
    def __init__(
        self,
        *,
        llm: LLMClient,
        registry: ToolRegistry,
        store: SessionStore,
        context_builder: ContextBuilder,
        trace: TraceLogger,
        max_steps: int = 6,
        parse_retries: int = 2,
    ) -> None:
        self.llm = llm
        self.registry = registry
        self.store = store
        self.context_builder = context_builder
        self.trace = trace
        self.parser = OutputParser()
        self.max_steps = max_steps
        self.parse_retries = parse_retries

    def _finalize(
        self, user_id: str, session_id: str, answer: str, trace_id: str, step: int
    ) -> str:
        self.store.add_message(user_id, session_id, "assistant", answer)
        self.trace.event(
            "final_answer",
            trace_id=trace_id,
            user_id=user_id,
            session_id=session_id,
            step=step,
            decision_type="final",
            answer=answer,
        )
        return answer

    def _request_decision(
        self,
        messages: list[dict[str, Any]],
        trace_id: str,
        step: int,
    ) -> Decision:
        working_messages = list(messages)
        for retry in range(self.parse_retries + 1):
            started = time.perf_counter()
            response = self.llm.complete(working_messages, self.registry.schemas())
            duration_ms = int((time.perf_counter() - started) * 1000)
            try:
                decision = self.parser.parse(response)
                self.trace.event(
                    "llm_decision",
                    trace_id=trace_id,
                    step=step,
                    retry_count=retry,
                    duration_ms=duration_ms,
                    decision_type=decision.type,
                    decision_summary=decision.decision_summary,
                )
                return decision
            except LLMOutputError as exc:
                self.trace.event(
                    "llm_output_invalid",
                    trace_id=trace_id,
                    step=step,
                    retry_count=retry,
                    duration_ms=duration_ms,
                    error=str(exc),
                )
                if retry >= self.parse_retries:
                    raise
                invalid_content = response.get("content")
                if not isinstance(invalid_content, str) or not invalid_content.strip():
                    invalid_content = "[模型返回了无法解析的空输出]"
                working_messages.append({"role": "assistant", "content": invalid_content})
                working_messages.append({"role": "system", "content": FORMAT_CORRECTION_PROMPT})
        raise LLMOutputError("模型输出无法解析")

    def run(self, user_id: str, session_id: str, user_input: str) -> str:
        user_input = user_input.strip()
        if not user_input:
            raise ValueError("用户输入不能为空")
        trace_id = uuid.uuid4().hex[:12]
        self.store.get_or_create_session(user_id, session_id)
        self.store.add_message(user_id, session_id, "user", user_input)
        self.trace.event(
            "request_started",
            trace_id=trace_id,
            user_id=user_id,
            session_id=session_id,
            step=0,
            user_input=user_input,
        )

        self.context_builder.maybe_compress(
            user_id, session_id, self.llm, self.trace, trace_id
        )
        previous_call_key: str | None = None

        for step in range(1, self.max_steps + 1):
            messages = self.context_builder.build(user_id, session_id)
            try:
                decision = self._request_decision(messages, trace_id, step)
            except (LLMError, LLMOutputError) as exc:
                answer = f"模型调用失败，本轮已安全终止：{exc}"
                self.trace.event(
                    "request_failed",
                    trace_id=trace_id,
                    user_id=user_id,
                    session_id=session_id,
                    step=step,
                    error=str(exc),
                )
                return self._finalize(user_id, session_id, answer, trace_id, step)

            if decision.type == "final":
                return self._finalize(
                    user_id,
                    session_id,
                    decision.answer or "模型未提供最终答案。",
                    trace_id,
                    step,
                )

            call = decision.tool_call
            if call is None:
                return self._finalize(
                    user_id, session_id, "模型返回了无效工具调用。", trace_id, step
                )
            call_key = f"{call.name}:{json.dumps(call.arguments, ensure_ascii=False, sort_keys=True)}"
            if call_key == previous_call_key:
                answer = f"检测到重复工具调用 {call.name}，本轮已终止以避免死循环。"
                self.trace.event(
                    "duplicate_tool_call",
                    trace_id=trace_id,
                    step=step,
                    tool_name=call.name,
                    tool_arguments=call.arguments,
                )
                return self._finalize(user_id, session_id, answer, trace_id, step)
            previous_call_key = call_key

            argument_text = json.dumps(call.arguments, ensure_ascii=False, sort_keys=True)
            self.store.add_message(
                user_id,
                session_id,
                "assistant",
                argument_text,
                tool_call_id=call.id,
                tool_name=call.name,
            )
            execution_context = ToolExecutionContext(
                user_id=user_id, session_id=session_id, trace_id=trace_id
            )
            started = time.perf_counter()
            try:
                result = self.registry.execute(call.name, call.arguments, execution_context)
            except ToolError as exc:
                result = ToolResult(False, str(exc), error_code=type(exc).__name__)
            except Exception as exc:
                result = ToolResult(False, f"工具执行异常: {exc}", error_code="TOOL_ERROR")
            duration_ms = int((time.perf_counter() - started) * 1000)
            result_text = json.dumps(result.as_dict(), ensure_ascii=False, default=str)
            self.store.add_message(
                user_id,
                session_id,
                "tool",
                result_text,
                tool_call_id=call.id,
                tool_name=call.name,
            )
            self.trace.event(
                "tool_executed",
                trace_id=trace_id,
                user_id=user_id,
                session_id=session_id,
                step=step,
                tool_name=call.name,
                tool_arguments=call.arguments,
                tool_result=result.as_dict(),
                duration_ms=duration_ms,
            )

        return self._finalize(
            user_id,
            session_id,
            f"任务超过最大执行轮次（{self.max_steps}），请缩小问题范围后重试。",
            trace_id,
            self.max_steps,
        )
