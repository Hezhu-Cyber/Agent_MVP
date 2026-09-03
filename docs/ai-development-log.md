# AI 辅助开发与问题解决记录

本项目使用 AI 辅助拆解需求、生成代码初稿和补充测试。我负责确定 MVP 范围、技术选型、人工验收及问题修正。以下记录保留实际开发中的主要 Prompt 和判断。

## 1. 明确 MVP 范围

**Prompt**

> 请拆解这道 Agent Runtime 笔试题，整理一个最小可用的开发计划。不能使用 LangGraph、OpenHands、OpenClaw，优先保证可以运行和演示。

**判断与结果**

选择 Python + SQLite，只实现核心 Loop、工具、Session、Context、异常、Trace 和测试，不扩展 RAG、多 Agent、流式输出等非必需功能。

## 2. 确定工具和 Mock 边界

**Prompt**

> search 可以 Mock 是什么意思？怎样实现既能演示 LLM 自主调用工具，又方便稳定测试？

**判断与结果**

LLM 使用真实 API；`search` 和 `weather` 返回固定模拟数据；`calculator` 和 `todo` 执行真实逻辑。这样避免依赖额外服务，同时保证多步流程可重复测试。

## 3. 实现工具注册和 Agent Loop

**Prompt**

> 实现 BaseTool、ToolRegistry 和核心 Agent Loop。每个工具提供名称、描述、参数 Schema 和执行函数；Runtime 负责解析工具调用、校验参数、执行工具并把结果交回 LLM。

**判断与结果**

Runtime 只负责流程控制，具体工具逻辑独立实现。`user_id`、`session_id` 由 Runtime 注入，不能由 LLM 传入。单次请求最多执行 6 步，并检测连续重复调用。

## 4. 实现 Session 和 Context

**Prompt**

> 使用 `user_id + session_id` 隔离会话，支持重启恢复、普通追问和带工具结果的追问。Context 过长时做基础摘要，数据库保留完整历史。

**判断与结果**

- 对话和摘要按 `user_id + session_id` 隔离。
- Todo 是用户级业务数据，按 `user_id` 隔离。
- 每次调用 LLM 前放入 System Prompt、历史摘要和最近消息。
- 未压缩消息超过 20 条时总结较早历史，保留最近 10 条原文。
- 不把 API Key、完整 Trace、其他 Session 消息和隐藏思维链放入 Context。

## 5. 增加异常处理和 Trace

**Prompt**

> 处理 LLM 超时、429、5xx、非法输出、工具参数错误、工具异常、重复调用和 Context 压缩失败。每次请求生成 trace_id，并记录 JSONL 日志。

**判断与结果**

可恢复的 LLM 错误最多重试 2 次；工具错误转为结构化结果交回 LLM。Trace 记录 Step、决策、工具参数、结果和耗时，但不记录 API Key。

## 6. 构建自动化测试

**Prompt**

> 使用 pytest 和 ScriptedLLM 测试直接回答、工具循环、多工具调用、Session 隔离、Context 压缩、安全性和异常处理；再增加三个默认跳过的真实 LLM 测试。

**判断与结果**

离线测试验证自研 Runtime，不依赖外部 API；真实测试覆盖 `calculator`、`search` 和 `weather → todo`。最终结果为 21 个离线测试和 3 个真实 LLM 测试通过。

## 7. 增加本地 Web UI

**Prompt**

> 在现有 Runtime 上增加最小网页界面，支持聊天、切换 Session、查看 Todo 和 Trace。保留 CLI，网页与 CLI 共用 SQLite，不增加复杂前端框架。

**判断与结果**

使用 Python 标准库 HTTP Server 和原生 HTML/CSS/JavaScript。Web UI 只是新的输入输出入口，不修改 Agent Runtime 主流程。

## 8. 人工验收发现的问题

### Todo 被误调用

输入“请记住项目代号是蓝鲸42”时，模型曾错误创建 Todo。

**修正 Prompt**

> 只有用户明确要求创建、查询或完成待办、任务、提醒时才调用 Todo。普通事实、名称、代号和偏好应使用 Session 历史记忆。

复测结果：普通记忆请求不调用工具；明确的“创建待办”请求仍能正常调用 Todo。

### Windows CLI 编码错误

模型回答包含 Emoji 时，Windows GBK 终端出现 `UnicodeEncodeError`。

**修正 Prompt**

> CLI 遇到当前终端无法编码的字符时应安全替换，不能因为打印模型回答而退出。

修复后带 Emoji 的回答不会导致 CLI 崩溃。

## 9. 最终验收

**Prompt**

> 按原始要求实际运行离线测试、真实 LLM 测试和网页端到端测试，并检查 Session、持久化、Trace 与敏感文件，不要只给出静态代码结论。

**结果**

- 21 个离线测试通过
- 3 个真实 LLM 测试通过
- Calculator、Search、Weather → Todo 调用成功
- 普通追问、工具追问和 Session 隔离通过
- `.env`、数据库、日志和虚拟环境未上传 GitHub
