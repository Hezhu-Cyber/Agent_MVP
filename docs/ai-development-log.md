# AI 辅助开发与问题解决记录

本项目使用 AI 辅助拆解需求、实现代码和补充测试。实际过程是先生成执行文档，再按文档完成 MVP，最后通过人工运行持续修正。

## 1. 先整理执行文档

**Prompt**

> 请帮我整理这道 Agent Runtime 笔试题的解题计划。要求从零完成，不能依赖 LangGraph、OpenHands、OpenClaw。保证 Agent 最小可用即可，并输出一份执行文档。

**处理**

AI 将题目拆成 Agent Loop、工具、真实 LLM、Session、Context、异常、Trace 和测试。我确认只完成可运行、可演示的 MVP，不扩展 RAG、多 Agent 和流式输出。

## 2. 按要求逐个检查模块设计

**Prompt**

> 请根据执行文档，逐个检查项目需要的模块是否覆盖了题目要求。
>
> 请分别检查 Agent Runtime、LLM Client、Output Parser、Tool Registry、Calculator、Search、Weather、Todo、Session Store、Context Builder、Trace 和测试。每个模块说明负责什么、对应哪条要求、还缺什么。先保证 MVP 完整，不增加非必需功能。

**处理**

AI 将笔试要求逐项映射到模块，确认核心 Loop、工具 Schema、Session 隔离、Context 压缩、异常和 Trace 都有对应实现位置，并补充了缺失的测试项。我根据检查结果确认使用 Python + SQLite、真实 LLM API，以及四个最小工具，不扩展非必需功能。

## 3. 按文档实现项目

**Prompt**

> 请按照这个执行文档帮我完成这个项目。
>
> 继续。

**处理**

AI 创建了自研 Agent Runtime、LLM Client、Output Parser、Tool Registry、四个工具、SQLite Store、Context 压缩、异常处理、Trace、CLI 和测试。我检查项目结构，确认核心流程没有使用现成 Agent 框架。

## 4. 定位代码并运行

**Prompt**

> 这个代码在哪？
>
> 请复制到 `C:\Users\manba\Desktop\Agent_MVP`。
>
> 怎么运行这个代码？

**处理**

AI 整理桌面项目并补充环境配置、依赖安装和启动说明。我在本地 `.env` 配置真实 LLM，API Key 没有提交到 Git。

## 5. 增加可视化界面

**Prompt**

> 请在这个代码基础上，再加个可视化界面。

**处理**

AI 增加本地 Web UI，支持聊天、切换 Session、查看 Todo 和 Trace。网页与 CLI 共用原来的 Agent Runtime 和 SQLite，没有重复实现核心流程。

## 6. 理解核心代码

项目运行后，我继续询问：

> 核心 Agent Runtime 是什么？Loop 大致步骤是什么？
>
> Session 管理是什么逻辑？Context 如何有效管理？
>
> 异常处理、Trace 和测试用例有哪些？

**处理**

通过代码和解释确认：对话按 `user_id + session_id` 隔离；Todo 按 `user_id` 隔离；每次调用 LLM 前按“System Prompt → 历史摘要 → 最近消息”构建 Context；工具调用和结果进入消息历史；项目不保存隐藏思维链。

## 7. 完整测试并修正问题

**Prompt**

> 请帮我测试这个项目是否符合预期要求。

**处理**

AI 实际运行离线测试、真实 LLM 测试和网页端到端测试，检查 Session、持久化、工具链、Context 压缩、Trace 和敏感文件。结果为：

```text
21 个离线测试通过
3 个真实 LLM 测试通过
```

### 问题一：Todo 误调用

输入“请记住项目代号是蓝鲸42”时，模型曾错误创建 Todo。

> 请收紧 Todo 调用提示词。只有用户明确要求创建、查询或完成待办、任务、提醒时才调用 Todo；普通信息使用 Session 历史记忆。

复测后，普通记忆不再调用 Todo，明确待办请求仍能正常执行。

### 问题二：Windows 终端编码

真实模型回答包含 Emoji 时，Windows GBK 终端出现 `UnicodeEncodeError`。随后增加安全输出处理，避免 CLI 因个别字符无法显示而退出。

## 8. 整理提交材料

**Prompt**

> 请部署到 GitHub，并写好 README，说明运行方式、系统设计、Memory 的召回时机与放置方式。
>
> README 是给面试官看的，请精简内容。

**处理**

AI 完善 `.gitignore`，确认 `.env`、数据库、日志和虚拟环境未被跟踪，并协助完成 GitHub 推送。README 最终只保留项目简介、运行方式、架构、Loop、Session/Memory、异常、Trace、测试和项目边界。

## 最终结果

- 代码仓库：[Hezhu-Cyber/Agent_MVP](https://github.com/Hezhu-Cyber/Agent_MVP)
- 核心 Runtime、工具调度、Session 和 Context 均自行实现
- CLI 与 Web UI 可运行
- 21 个离线测试、3 个真实 LLM 测试通过
- `.env`、数据库和 Trace 日志未上传
