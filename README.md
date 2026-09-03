# Mini Agent Runtime

一个从零实现的最小可用 Agent Runtime。项目不依赖 LangGraph、OpenHands、OpenClaw 或其他 Agent 框架，核心循环、工具注册、输出解析、Session、Context 压缩和 Trace 均自行实现。

## 已实现功能

- 真实 LLM API 接入（OpenAI-compatible Chat Completions）
- LLM 自主决定直接回答或调用工具
- 单工具逐步循环：`LLM → Tool → LLM → ... → Final`
- 工具注册机制：名称、描述、JSON Schema、执行函数
- `calculator`：安全数学表达式计算
- `search`：稳定的本地 Mock 搜索
- `todo`：创建、查询、完成用户待办
- `weather`：用于复合任务演示的 Mock 天气
- `user_id + session_id` 窗口隔离
- SQLite 持久化，重启后可继续会话
- 普通追问及携带工具结果的追问
- 超过 20 条未压缩消息时生成基础摘要
- 最大 6 步、重复工具调用检测、格式纠正和基础重试
- 终端 Trace 与 JSONL 执行日志
- 本地网页控制台：聊天、Session 切换、Todo 和 Trace 面板
- 离线自动化测试和可选真实 LLM 测试

## 明确不包含

- 向量数据库、Embedding、RAG
- 并行工具调用、流式输出
- 多 Agent、规划器、子任务系统
- 登录鉴权或生产级权限系统

这些内容不是本笔试 MVP 的验收必需项。

## 系统结构

```text
CLI / Web UI
  ↓
SessionStore (SQLite)
  ↓
ContextBuilder (摘要 + 最近消息)
  ↓
AgentRuntime Loop
  ├── OpenAIChatClient
  ├── OutputParser
  ├── ToolRegistry
  │   ├── calculator
  │   ├── search (Mock)
  │   ├── todo
  │   └── weather (Mock)
  └── TraceLogger
```

核心循环位于 `agent/runtime.py`。模型客户端只负责发送和接收请求，不负责执行工具或管理状态。

### 核心模块职责

| 模块 | 职责 |
|---|---|
| `agent/runtime.py` | 控制 LLM → Tool → LLM 循环、最大步数和终止条件 |
| `agent/context.py` | 召回 Session 历史、拼装 Context、触发基础压缩 |
| `agent/parser.py` | 解析最终答案和工具调用 |
| `tools/registry.py` | 注册工具、导出 Schema、校验参数并执行工具 |
| `memory/store.py` | 使用 SQLite 持久化 Session、Message 和 Todo |
| `llm/client.py` | 调用真实 OpenAI-compatible LLM API |
| `tracing/logger.py` | 输出终端 Trace 并追加写入 JSONL 日志 |

一次请求的主流程：

```text
接收用户输入并持久化
→ 召回当前 Session Context
→ 将 Context 与工具 Schema 发送给 LLM
→ 解析为 Final 或 Tool Call
→ 如果是 Tool Call：校验参数、执行、保存结果并进入下一步
→ 如果是 Final：保存答案并返回
→ 达到 6 步或检测到重复调用时安全终止
```

## 环境要求

- Python 3.11+
- 一个支持 Tool Calling 的真实 LLM API

应用代码仅依赖 Python 标准库。只有运行测试时需要安装 `pytest`。

## 从零运行

### 1. 创建环境

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS / Linux：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置真实 LLM

复制环境变量模板：

```powershell
Copy-Item .env.example .env
```

编辑 `.env`：

```dotenv
LLM_API_KEY=你的真实API密钥
LLM_MODEL=你的模型名称
LLM_BASE_URL=https://api.openai.com/v1
LLM_TIMEOUT_SECONDS=60
```

`LLM_MODEL` 不提供硬编码默认值，避免因为模型权限或服务商差异导致误用。请选择账户实际可用且支持工具调用的模型。

### 3. 启动可视化界面（推荐）

```powershell
python web_app.py
```

浏览器打开：`http://127.0.0.1:8765`

页面左侧可填写 `user_id` 和 `session_id`，点击“载入会话”即可在不同窗口之间切换；中间用于聊天；右侧显示当前用户的 Todo、最近 Trace 和 Runtime 状态。网页与 CLI 共用 `data/agent.db`，因此在任一入口继续对话都能读取同一 Session。

可选启动参数：

```powershell
python web_app.py --host 127.0.0.1 --port 8765
```

这是本地开发界面，默认只监听本机地址，不包含登录鉴权，请勿直接暴露到公网。

### 4. 启动 CLI 窗口

```powershell
python app.py --user user_a --session window_1
```

输入 `exit` 或 `quit` 退出。

也可以只运行一条消息：

```powershell
python app.py --user user_a --session window_1 --message "请计算 17 乘 23"
```

### 5. 演示两个独立 Session

终端一：

```powershell
python app.py --user user_a --session window_1
```

终端二：

```powershell
python app.py --user user_a --session window_2
```

两个窗口的对话历史相互隔离。Todo 是用户级业务数据，因此同一用户可以在两个窗口查询自己创建的待办。

## 推荐演示对话

### 直接回答

```text
你好，你能做什么？
```

### Calculator

```text
请使用工具计算 17 * 23。
```

### 多步工具调用

```text
查一下明天上海天气，如果下雨就帮我创建一个“出门带伞”的待办。
```

预期路径：

```text
weather → 读取天气结果 → todo.create → final
```

`search` 和 `weather` 是 Mock 工具，回答中会明确说明不是实时数据。LLM 调用本身是真实 API。

## 工具注册机制

每个工具继承 `BaseTool`，提供：

- `name`
- `description`
- `parameters_schema`
- `execute(arguments, context)`

`ToolRegistry` 会把 Schema 传给 LLM，并在执行前完成必填字段、类型、枚举、长度、范围及额外字段校验。

`ToolExecutionContext` 由 Runtime 注入：

```python
ToolExecutionContext(
    user_id="user_a",
    session_id="window_1",
    trace_id="...",
)
```

LLM 无法通过工具参数伪造 `user_id`，Todo 只允许访问当前用户的数据。

## Session 与 Memory

SQLite 默认保存在 `data/agent.db`，包含三张表：

- `sessions`：窗口、摘要、压缩位置
- `messages`：用户消息、助手消息、工具调用和工具结果
- `todos`：用户级待办

所有对话消息都使用 `user_id + session_id` 查询，因此同一用户的多个窗口不会串话。

Memory 按用途分层：

| 信息 | 保存位置 | 作用域 | 是否直接进入 Context |
|---|---|---|---|
| 对话消息、工具调用、工具结果 | SQLite `messages` | `user_id + session_id` | 是，按摘要和最近消息召回 |
| 较早对话摘要 | SQLite `sessions.summary` | `user_id + session_id` | 是，作为 System Message 放置 |
| Todo | SQLite `todos` | `user_id` | 否，需要时调用 `todo` 查询 |
| 执行 Trace | `logs/traces.jsonl` | `trace_id` | 否，仅用于调试和审计 |

### Memory 的召回时机

每一个 Agent Step 调用 LLM 前都会重新召回，而不是只在收到用户输入时召回一次。因此工具执行结果保存后，下一步 LLM 调用可以立即读到该结果。召回内容为：

1. System Prompt
2. 当前 Session 的历史摘要（若存在）
3. 当前 Session 最近的原始消息
4. 当前任务中的工具调用和工具结果

Todo 等可靠业务状态不会被盲目塞进 Prompt；需要时由 LLM 调用 `todo list` 从数据库读取。

以下内容不会放进 Context：API Key、完整 Trace、其他 Session 的消息、全部 Todo，以及模型的隐藏思维链。项目只保留简短的公开决策摘要。

### Context 放置方式

```text
System Prompt
→ 较早历史摘要
→ 最近 user / assistant / tool 消息（保持原始顺序）
```

工具定义通过 API 的 `tools` 字段独立传入。

### 基础压缩

当当前 Session 的未压缩消息超过 20 条时：

1. 保留最近 10 条原始消息。
2. 将更早消息与已有摘要交给真实 LLM。
3. 生成固定结构的摘要并保存到 `sessions.summary`。
4. 数据库仍保留全部原始消息，只减少后续发给模型的内容。

摘要包含：已确认事实、用户偏好、已完成动作、未完成事项和重要引用。

如果摘要请求失败，Agent 会记录 Trace，并使用最近 20 条消息继续工作。

## 输出解析

`OutputParser` 支持：

- API 原生 `tool_calls`
- 普通文本最终回答
- 执行文档约定的结构化 `final` / `tool_call` JSON
- Markdown 代码块包裹的结构化最终回答

项目不保存完整隐藏思维链，只记录简短的 `decision_summary`。

## 异常和循环保护

- LLM 网络错误、429、5xx：最多重试 2 次
- 非法模型输出：追加格式纠正消息，最多重试 2 次
- 未注册工具、参数错误、工具异常：转成结构化工具错误交回 LLM
- 相同工具和相同参数连续调用：第二次时终止
- 每次用户请求最多执行 6 个 Agent Step
- SQLite 写入使用事务，异常时自动回滚

## Trace

默认日志文件：`logs/traces.jsonl`。

每条记录包含：

- `trace_id`
- `user_id`、`session_id`
- `step`、`event_type`
- `decision_type`、`decision_summary`
- 工具名称、参数、结果摘要
- 执行耗时、重试次数和错误

API Key 不会写入日志。过长字符串会被截断。

## 测试

### 离线测试

```powershell
python -m pytest -q -m "not live_llm"
```

离线测试使用脚本化 LLM，验证的是自行实现的 Runtime 行为，包括：

- 直接回答
- Calculator 调用
- Weather → Todo 多步循环
- 工具错误反馈
- 重复调用终止
- Session 隔离和重启恢复
- Context 压缩
- Calculator 安全性

### 真实 LLM 测试

真实测试可能产生费用，默认跳过：

```powershell
$env:RUN_LIVE_LLM="1"
python -m pytest -q -m live_llm
```

必须同时提供 `LLM_API_KEY` 和 `LLM_MODEL`。

当前验收基线：21 个离线测试通过，3 个真实 LLM 测试通过。真实测试会产生 API 调用费用。

## 项目目录

```text
.
├── app.py
├── web_app.py
├── web/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── agent/
│   ├── context.py
│   ├── models.py
│   ├── parser.py
│   ├── prompts.py
│   └── runtime.py
├── llm/
│   ├── base.py
│   └── client.py
├── memory/
│   └── store.py
├── tools/
│   ├── base.py
│   ├── registry.py
│   ├── calculator.py
│   ├── search.py
│   ├── todo.py
│   └── weather.py
├── tracing/
│   └── logger.py
├── tests/
├── docs/
│   ├── design.md
│   ├── prompts.md
│   └── ai-development-log.md
├── .env.example
├── pytest.ini
└── requirements.txt
```

## 已知限制

- LLM 接口使用 OpenAI-compatible Chat Completions 格式，不自动适配其他协议。
- 每次只执行一个工具调用；如果模型返回多个，只处理第一个。
- Search 与 Weather 使用固定 Mock 数据，不提供实时信息。
- 摘要是基础压缩，未实现语义检索和复杂长期记忆。
- 用户身份来自 CLI 参数或网页输入，未实现登录鉴权。

## 提交与录屏

建议按以下顺序录制：

1. 展示 README、依赖和核心 Runtime。
2. 启动 CLI，演示直接回答。
3. 演示 Calculator 并展示 Trace。
4. 演示 Weather → Todo。
5. 启动两个 Session，证明上下文隔离。
6. 重启后继续原 Session。
7. 运行离线测试。

Prompt 见 `docs/prompts.md`，AI 辅助开发记录见 `docs/ai-development-log.md`。
