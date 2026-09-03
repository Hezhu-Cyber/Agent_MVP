# AI 辅助开发与问题解决记录

本项目使用 AI 辅助拆解需求、实现代码和补充测试。实际过程是先生成执行文档，再按文档完成 MVP，最后通过人工运行持续修正。

## 1. 先整理执行文档

**Prompt**

> 你先作为一名熟悉 LLM Tool Calling 的 Python 架构师，帮我分析这道 Agent Runtime 笔试题。当前阶段不要写代码，先把题目转成一份可执行的 MVP 开发文档。
>
> 约束：核心流程必须从零实现，不能使用 LangGraph、OpenHands、OpenClaw 等 Agent 框架；优先使用 Python 标准库和 SQLite；只做验收必需功能，不扩展 RAG、多 Agent、任务规划等内容。
>
> 请按“需求拆解 → 模块划分 → 数据结构 → Agent Loop → Context 策略 → 异常与 Trace → 测试方案 → 交付清单”的顺序输出。每项标明对应的题目要求、最小实现方式和验收方法。对存在取舍的地方给出推荐方案和理由。
>
> 最终文档需要让开发者可以按步骤直接实施，并明确完成标准和暂不实现的边界。

**处理**

AI 将题目拆成 Agent Loop、工具、真实 LLM、Session、Context、异常、Trace 和测试。我确认只完成可运行、可演示的 MVP，不扩展 RAG、多 Agent 和流式输出。

## 2. 按要求逐个检查模块设计

**Prompt**

> 现在以执行文档为基线做一次实现前审查。不要直接补代码，先建立“题目要求—模块—验收用例”的对应关系，找出遗漏和不必要设计。
>
> 请逐个检查 Agent Runtime、LLM Client、Output Parser、Tool Registry、Calculator、Search、Weather、Todo、Session Store、Context Builder、Trace Logger 和 tests。
>
> 对每个模块回答：
>
> 1. 它解决哪条题目要求；
> 2. 最小职责和输入输出是什么；
> 3. 与其他模块的边界是什么；
> 4. 最容易遗漏的异常或测试是什么；
> 5. 当前应保留、调整还是删除。
>
> 最后输出一张优先级清单，将问题分为“阻塞验收、应该修正、可暂不实现”。不要为了完整感增加题目未要求的框架和基础设施。

**处理**

AI 将笔试要求逐项映射到模块，确认核心 Loop、工具 Schema、Session 隔离、Context 压缩、异常和 Trace 都有对应实现位置，并补充了缺失的测试项。我根据检查结果确认使用 Python + SQLite、真实 LLM API，以及四个最小工具，不扩展非必需功能。

## 3. 按文档实现项目

**Prompt**

> 请按照已经确认的执行文档，在当前目录从零完成最小可用 Agent Runtime。先检查现有文件，再按依赖顺序实施，不要只输出示例代码或伪代码。
>
> 实现约束：
>
> - 不使用任何现成 Agent 框架；
> - Runtime、工具注册、输出解析、Session 和 Context 必须自行实现；
> - 使用真实 OpenAI-compatible LLM API，密钥只从 `.env` 读取；
> - Search 和 Weather 可以 Mock，但回答必须明确标注；
> - 会话使用 `user_id + session_id` 隔离并持久化到 SQLite；
> - 工具结果必须回填 Context，支持继续调用工具；
> - 实现最大步数、重复调用检测、基本重试和 JSONL Trace；
> - 应用代码优先使用标准库，测试使用 pytest。
>
> 请按 Store → Tools/Registry → LLM/Parser → Context → Runtime → CLI → Tests 的顺序推进。每完成一个阶段就运行相关测试；遇到失败先定位根因再修改，不要绕过测试。
>
> 完成后给出实际文件位置、运行命令、测试结果和已知限制。如果任务尚未完成，请继续实施，不要提前宣布完成。

**处理**

AI 创建了自研 Agent Runtime、LLM Client、Output Parser、Tool Registry、四个工具、SQLite Store、Context 压缩、异常处理、Trace、CLI 和测试。我检查项目结构，确认核心流程没有使用现成 Agent 框架。

## 4. 增加可视化界面

**Prompt**

> 请在现有 Agent Runtime 上增加一个最小可用的本地 Web UI，同时保留 CLI。先复用现有 Runtime、SessionStore 和 SQLite，不要在网页后端重复实现 Agent Loop。
>
> 页面按内部运行控制台设计：左侧输入并切换 `user_id`、`session_id`；中间显示对话和发送消息；右侧显示 Todo、最近 Trace、当前模型和 Runtime 状态。需要支持刷新后重新加载原 Session。
>
> 技术上优先使用 Python 标准库 HTTP Server 和原生 HTML/CSS/JavaScript，不增加大型依赖。后端至少提供 health、session、chat、complete todo 接口，并校验 JSON、字段长度和错误状态。服务默认只监听 `127.0.0.1`。
>
> 修改后需要保留原有测试，再增加 Web API 测试。实际启动服务并请求健康接口，确认页面资源、Runtime 和数据库能够正常工作。

**处理**

AI 增加本地 Web UI，支持聊天、切换 Session、查看 Todo 和 Trace。网页与 CLI 共用原来的 Agent Runtime 和 SQLite，没有重复实现核心流程。

## 5. 理解核心代码

项目运行后，我使用下面的 Prompt 逐段理解代码，而不是只看功能结果：

> 请作为代码讲解者，基于当前仓库的真实实现帮我做一次面试式代码走查，不要给通用概念答案，也不要修改代码。
>
> 请按一次请求的执行顺序说明：用户输入从哪里进入、如何定位 Session、Context 在哪里构建、LLM 如何得到工具 Schema、工具调用如何解析和执行、工具结果如何回填、最终答案如何保存。每一步引用对应的文件、类或函数。
>
> 然后重点回答：
>
> - `user_id + session_id` 为什么能隔离两个窗口；
> - 普通追问和工具追问分别依赖哪些消息；
> - Context 超过阈值后如何压缩，哪些信息不应进入 Context；
> - 最大步数、重复调用、参数错误和 LLM 异常在哪里处理；
> - Trace 如何把一次请求中的多个 Step 关联起来；
> - 现有测试分别证明了什么，还有哪些只能人工验证。
>
> 如果文档描述与代码不一致，以代码为准并明确指出差异。

**处理**

通过代码和解释确认：对话按 `user_id + session_id` 隔离；Todo 按 `user_id` 隔离；每次调用 LLM 前按“System Prompt → 历史摘要 → 最近消息”构建 Context；工具调用和结果进入消息历史；项目不保存隐藏思维链。

## 6. 完整测试并修正问题

**Prompt**

> 请以面试验收人的角度，对当前项目做一次基于证据的完整验收。不要只阅读代码后判断“应该可以”，必须实际运行测试和关键链路。
>
> 先把原始要求整理成检查表，然后依次验证：没有引入 Agent 框架、真实 LLM 可用、直接回答、Calculator、Search、Weather → Todo、多 Session 隔离、重启恢复、普通追问、工具追问、Context 压缩、异常保护、Trace、Web API 和敏感文件排除。
>
> 自动化部分分别运行离线测试和真实 LLM 测试；端到端部分使用独立的测试用户、Session、数据库和 Trace，避免污染已有数据。每项记录输入、预期、实际结果和证据。失败时区分代码缺陷、环境问题和测试问题，不要为了通过而降低断言。
>
> 最终按“通过、部分通过、未通过、提交物缺失”四类输出结论，并列出提交前必须修复的问题。

**处理**

AI 实际运行离线测试、真实 LLM 测试和网页端到端测试，检查 Session、持久化、工具链、Context 压缩、Trace 和敏感文件。结果为：

```text
21 个离线测试通过
3 个真实 LLM 测试通过
```

### 问题一：Todo 误调用

输入“请记住项目代号是蓝鲸42”时，模型曾错误创建 Todo。

> 请修正 Todo 的调用边界，不要修改 Runtime 主流程。只有用户明确表达“创建/查看/完成待办、任务、提醒”或“提醒我……”时才允许调用 Todo；“记住名称、代号、偏好、事实、聊天背景”应保留在 Session 历史中，禁止转成 Todo；意图不明确时先询问。
>
> 修改后用真实 LLM 做正反例测试：反例“请记住项目代号是蓝鲸42”不得产生工具消息或 Todo；正例“请创建一个待办：明天提交作业”必须调用 Todo。最后检查工具轨迹和数据库，而不能只根据自然语言回答判断。

复测后，普通记忆不再调用 Todo，明确待办请求仍能正常执行。

### 问题二：Windows 终端编码

真实模型回答包含 Emoji 时，Windows GBK 终端出现 `UnicodeEncodeError`。

> 请先根据堆栈确认异常发生在业务执行还是最终输出阶段。如果工具和数据库操作已经成功，只修复 CLI 的输出边界，不修改模型结果和 Agent Loop。
>
> 方案需要兼容 Windows 当前控制台编码：可显示字符保持原样，无法编码的字符安全替换，不能因打印 Emoji 导致进程退出。修改后用包含 Emoji 的真实模型回答复测，并检查 CLI 退出码为 0。

修正后，CLI 不再因个别字符无法显示而退出。

## 最终结果

- 代码仓库：[Hezhu-Cyber/Agent_MVP](https://github.com/Hezhu-Cyber/Agent_MVP)
- 核心 Runtime、工具调度、Session 和 Context 均自行实现
- CLI 与 Web UI 可运行
- 21 个离线测试、3 个真实 LLM 测试通过
- `.env`、数据库和 Trace 日志未上传
