---
name: C08_数据代理分析
description: 当用户要用阿里云 Data Agent 查询数据库、分析文件或生成数据报告时使用；通过本地 CLI 执行并追踪会话。
---

# C08_数据代理分析

## 这项技能解决什么问题

- 使用阿里云 Data Agent for Analytics 做自然语言数据查询、数据库分析、文件分析和报告生成
- 通过本地 `scripts/data_agent_cli.py` 完成数据源发现、DMS 导入、会话创建、进度追踪、报告获取
- 把外部 `alibabacloud-data-agent-skill` 本地化为当前工作区的中文薄入口

## 先读哪些本地知识

- 先读 `references/本地适配说明.md`，确认路径、依赖及来源授权的适用范围。

- 先读 `references/WORKFLOWS.md`，确认本次属于已有 Data Center 数据库、DMS 导入、文件分析还是会话复用
- 需要完整命令参数时，再读 `references/COMMANDS.md`
- 使用 `ANALYSIS` 或 `INSIGHT` 深度分析模式前，读 `references/ANALYSIS_MODE.md`
- 涉及账号权限、RAM 策略或最小权限时，读 `references/RAM-POLICIES.md`
- 需要核对外部原始说明时，再读 `references/原始技能说明.md`

## 固定动作

1. 先判断用户目标：列数据源、查询数据库、导入 DMS 数据库、分析文件、追踪会话、获取报告或管理 workspace/custom agent。
2. 确认运行环境：Python 3.10+、虚拟环境、`scripts/requirements.txt` 依赖、阿里云凭证或 `DATA_AGENT_API_KEY`。
3. 默认在 `.agents/skills/C08_数据代理分析/` 目录下运行 CLI，避免路径漂移。
4. 首次使用先运行 `ls` 或 `workspace` 做只读发现；目标库不在 Data Agent Data Center 时，按 `dms` → `import` → `db` 顺序处理。
5. 创建分析会话后，记录 `Session ID`；后续追问、确认计划、恢复进度统一使用 `attach --session-id`。
6. 深度 `ANALYSIS` / `INSIGHT` 模式涉及长时间执行、计划确认或报告生成时，先向用户说明成本和等待时间，再继续。

## 什么时候再读本 skill 的 references

- 需要端到端操作示例时，读 `references/WORKFLOWS.md`
- 需要查子命令参数、环境变量和模式差异时，读 `references/COMMANDS.md`
- 需要解释计划确认、异步执行和 `attach` 恢复机制时，读 `references/ANALYSIS_MODE.md`
- 需要配置 RAM 权限时，读 `references/RAM-POLICIES.md`
- 需要确认迁入来源和本地化动作时，读 `references/迁移说明.md`

## 边界

- 不在未确认凭证与权限的情况下执行会访问企业数据库或文件数据的命令
- 不把 AK/SK、API Key、Session Token、`.env` 明文写入 output、日志或最终回复
- 不默认执行导入、长时间深度分析、报告渲染或高成本任务；需要先确认用户意图
- 不把 Data Agent 会话结果当作本地工作区标准或数据库事实源，结论需要标明来源与时间
- 不把外部原始长说明搬回薄 `SKILL.md`
