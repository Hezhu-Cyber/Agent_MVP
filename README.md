# Agent_MVP

> 项目材料：AI Prompt 与问题解决记录见 [`AI Prompt 与问题解决记录.md`](AI%20Prompt%20与问题解决记录.md)，架构设计题见 [`架构设计题.md`](架构设计题.md)。

一个从零实现的最小可用 Agent Runtime。核心循环、工具调度、Session、Context 压缩和 Trace 均自行实现，**不依赖 LangGraph、OpenHands、OpenClaw 等 Agent 框架**。

## 功能

- 接入真实 OpenAI-compatible LLM API
- LLM 基于 JSON Schema 自主决定直接回答或调用工具
- 4 个工具：`calculator`、`search`（Mock）、`weather`（Mock）、`todo`
- `user_id + session_id` 会话隔离与 SQLite 持久化
- 支持普通追问和带工具结果的追问
- 基础 Context 压缩、最大步数、重复调用检测和异常重试
- CLI 与本地 Web UI
- 终端 Trace 和 JSONL 执行日志

## 快速运行

环境要求：Python 3.11+。

```powershell
git clone https://github.com/Hezhu-Cyber/Agent_MVP.git
cd Agent_MVP
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

编辑 `.env`：

```dotenv
LLM_API_KEY=你的API密钥
LLM_MODEL=支持工具调用的模型名称
LLM_BASE_URL=https://api.openai.com/v1
LLM_TIMEOUT_SECONDS=60
```

启动 Web UI：

```powershell
python web_app.py
```

访问 `http://127.0.0.1:8765`。

启动 CLI：

```powershell
python app.py --user user_a --session window_1
```

## 系统设计

```text
CLI / Web UI
      ↓
AgentRuntime Loop
  ├── ContextBuilder ── SessionStore (SQLite)
  ├── OpenAIChatClient
  ├── OutputParser
  ├── ToolRegistry ── calculator / search / weather / todo
  └── TraceLogger ── console + logs/traces.jsonl
```

核心 Loop：

```text
接收并保存用户输入
→ 构建当前 Session Context
→ 将 Context 和工具 Schema 发送给 LLM
→ 解析 Final Answer 或 Tool Call
→ 如果调用工具：校验参数、执行、保存结果并继续 Loop
→ 如果得到最终答案：保存并返回
```

每次请求最多执行 6 个 Step；连续重复相同工具调用时提前终止，避免死循环。

## 工具机制

每个工具提供 `name`、`description`、`parameters_schema` 和 `execute()`。`ToolRegistry` 将 Schema 传给 LLM，并负责参数校验和执行。用户与 Session 身份由 Runtime 注入，不能由 LLM 伪造。

## Session 与 Memory

### 数据作用域

| 数据 | 作用域 | 存储位置 |
|---|---|---|
| 对话、工具调用、工具结果 | `user_id + session_id` | SQLite `messages` |
| 历史摘要 | `user_id + session_id` | SQLite `sessions` |
| Todo | `user_id` | SQLite `todos` |
| 执行日志 | `trace_id` | `logs/traces.jsonl` |

因此，同一用户的 `window_1` 和 `window_2` 对话不会串话；Todo 属于用户级业务数据，可以跨窗口查询。

### Memory 召回时机

**每次调用 LLM 前**都会重新构建 Context。工具结果写入数据库后，下一次 Loop 调用 LLM 时即可读到，因此支持基于工具结果继续决策。

### Context 放置方式

```text
System Prompt
→ 当前 Session 的较早历史摘要（若存在）
→ 当前 Session 最近的 user / assistant / tool 消息
```

工具 Schema 通过 API 的 `tools` 字段单独传入。Todo 等可靠业务状态不直接塞入 Context，需要时通过工具从数据库读取。

项目不保存隐藏思维链；API Key、完整 Trace、其他 Session 消息和全部 Todo 也不会进入 Context。

### 基础压缩

当未压缩消息超过 20 条时，较早消息被总结到 `sessions.summary`，最近 10 条消息保留原文。SQLite 仍保存完整历史，只减少后续发送给模型的 Token。

## 异常与 Trace

LLM 网络错误和非法输出最多重试 2 次；工具参数或执行错误会转为结构化结果交回 LLM。每次请求生成唯一 `trace_id`，记录 Step、工具参数、结果、耗时和错误，且不记录 API Key。

## 测试

离线测试：

```powershell
python -m pytest -q -m "not live_llm"
```

真实 LLM 测试：

```powershell
$env:RUN_LIVE_LLM="1"
python -m pytest -q -m live_llm
```

当前验收结果：**21 个离线测试通过，3 个真实 LLM 测试通过**。

## 边界

- `search` 和 `weather` 使用 Mock 数据，不代表实时信息
- 每个 Step 只执行一个工具调用
- 未实现流式输出、向量检索、多 Agent 和生产级鉴权

详细设计见 [`docs/design.md`](docs/design.md)，Prompt 见 [`docs/prompts.md`](docs/prompts.md)。
