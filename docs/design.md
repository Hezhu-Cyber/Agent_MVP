# 系统设计说明

## 设计目标

在不依赖 Agent 框架的前提下，以尽可能少的组件实现可运行、可解释、可测试的 Agent Loop。

## 关键决策

### 1. 使用直接 HTTP 模型客户端

`OpenAIChatClient` 使用 Python 标准库调用 OpenAI-compatible Chat Completions API。这样可以清晰证明工具循环、状态管理和错误处理不是由 SDK 或 Agent 框架代为完成。

模型名称必须由 `LLM_MODEL` 指定，项目不猜测账户可用模型。

### 2. 每次只执行一个工具

MVP 不实现并行调用。模型收到明确指令：每次只选择一个工具，等待结果后再决定下一步。这样让 Trace 和状态转换更容易检查。

### 3. 数据库保留原始消息

压缩只影响发送给 LLM 的 Context，不删除数据库中的原始记录。这样既能控制上下文，也能保留审计能力。

### 4. 对话状态和业务状态分离

- 对话消息：属于 `user_id + session_id`
- Todo：属于 `user_id`

因此窗口历史不会串话，但同一用户可以跨窗口查看自己的待办。

### 5. 工具身份由 Runtime 注入

LLM 只能提供工具业务参数，不能提供 `user_id`、`session_id` 或 `trace_id`。这些值由 Runtime 生成 `ToolExecutionContext`，降低越权风险。

## 状态流转

```text
USER_INPUT
  → LOAD_SESSION
  → MAYBE_COMPRESS
  → BUILD_CONTEXT
  → CALL_LLM
      ├─ FINAL → SAVE_ANSWER → RETURN
      └─ TOOL_CALL
           → VALIDATE
           → EXECUTE
           → SAVE_TOOL_RESULT
           → BUILD_CONTEXT
           → CALL_LLM
```

## 数据表

### sessions

组合唯一键：`user_id + session_id`。保存摘要和 `summarized_through` 游标。

### messages

保存 `user`、`assistant`、`tool` 三种角色。工具调用消息额外保存 `tool_call_id` 和 `tool_name`，以便重建模型 API 所需的消息结构。

### todos

按 `user_id` 隔离，保存来源 Session 便于审计。

## 失败策略

可恢复错误尽量反馈给 LLM 修正；不可恢复错误转成用户可读的最终回答。无论成功或失败，关键步骤都会写入 JSONL Trace。
