# HTML 技能包适装安装记录

> 记录 `f-labs-io/agent-html-skills` 在当前工作区中的适装评估、本地化安装决策与落地结果。  
> 执行日期：2026-05-17

---

## 一、输入与来源

- 用户请求：通过 `A02_安装技能_v1.0.0` 安装 `https://github.com/f-labs-io/agent-html-skills`
- 来源仓库：`f-labs-io/agent-html-skills`
- 抓取方式：A02 清单脚本未找到默认 `skills/.curated` 路径后，改用 git 临时克隆检查仓库结构；随后用 A02 安装脚本创建本地目标 Skill 骨架。
- 来源提交：`5d8025b5216a8710fed8f40d7a379833f43af607`
- 提交时间：`2026-05-13T19:30:06+03:00`

原仓库不是单个 Skill，而是一个 Claude Code 插件包：`plugins/html-skills/skills/` 下包含 16 个 HTML 产物类 Skill，并带有共享 `submit-handler.js` 和 Claude Code 本地监听辅助能力。

---

## 二、适装评估

| 维度 | 评估 |
|---|---|
| 新增知识价值 | 高。它补充的是 HTML 产物模式库，能把长 Markdown 报告、图示、矩阵、时间线、数据探索和互动编辑器转成更适合浏览器审阅的表达。 |
| 能力重叠度 | 中。与通用前端开发能力有交集，但它更偏“输出形态选择与结构规则”，不是完整 Web App 工程。 |
| 运行环境耦合度 | 中偏高。原仓库的自动回传依赖 Claude Code 的本地监听、Monitor 与 TaskStop；当前 Codex 工作区不应把这些机制作为运行前提。 |
| 流程负担 | 原样安装 16 个 runtime Skill 会显著加重触发面；聚合成一个 G01 薄入口后负担可控。 |
| 触发范围 | 应限制为用户需要 HTML 报告、图示、可视化决策或互动编辑器时，不应干扰普通问答、代码修改和工作区治理流程。 |
| 上下文成本 | 原始说明较长且每个 Skill 重复 HTML foundation。保留到 references，按需读取更合适。 |

结论：条件安装。

建议范围：当前项目项目级聚合安装，不做 16 个独立入口的全量注册。

---

## 三、本地安装决策

本次没有把外部 16 个 Skill 逐一注册为 `G01` 到 `G16`，而是安装为一个项目级聚合 Skill：

```text
.agents/skills/G01_HTML交互产物_v1.0.0/
```

这样做的原因：

- 保留完整外部知识，但只暴露一个触发入口，避免日常任务误触发。
- 当前工作区已有严格的 B01/B02/B03/B08 强制门，外部 Skill 不应绕过这些门。
- 原仓库的监听回传链路是 Claude Code 专属机制，直接迁入会形成运行环境假设。
- 聚合入口能让本地 `SKILL.md` 保持薄入口，详细规则留在 references 中。

---

## 四、落地结果

新增 Skill：

- `G01_HTML交互产物_v1.0.0`

新增或更新的关键文件：

- `.agents/skills/G01_HTML交互产物_v1.0.0/SKILL.md`
- `.agents/skills/G01_HTML交互产物_v1.0.0/agents/openai.yaml`
- `.agents/skills/G01_HTML交互产物_v1.0.0/references/HTML产物模式索引.md`
- `.agents/skills/G01_HTML交互产物_v1.0.0/references/迁移说明.md`
- `.agents/skills/G01_HTML交互产物_v1.0.0/references/原始技能包/skills/`
- `.agents/skills/G01_HTML交互产物_v1.0.0/assets/submit-handler.js`
- `.agents/skills/G01_HTML交互产物_v1.0.0/assets/web-probe.py`
- `.claude/commands/G01_HTML交互产物_v1.0.0.md`
- `.system/standards/workspace-spec.json`
- `.system/standards/Skills管理标准.md`

注册变化：

- `workspace-spec.json` 版本更新到 `1.20.0`
- `skillsManagement.registeredSkills` 追加 `G01_HTML交互产物_v1.0.0`
- `Skills管理标准.md` 版本更新到 `1.13.0`
- 新增 G 域：HTML产物

---

## 五、本地边界

当前工作区中使用 G01 时：

- 默认生成单文件 HTML，便于浏览器打开和审阅。
- 互动类产物默认走剪贴板回传，不启动 Claude Code 专属监听器。
- 需要详细规则时只读取对应原始 Skill，不一次性展开整个原始技能包。
- 涉及当前项目知识输出时，仍必须落到 `output/`，并执行 B02/B03/B08。

不建议：

- 把 `html-skills-listen` 与 `html-skills-stop` 注册成当前项目 runtime Skill。
- 将 16 个原始 Skill 原样加入注册表。
- 在普通短答或代码修复任务中强行输出 HTML。

---

## 六、后续建议

- 若后续频繁使用其中某一类 HTML 产物，再考虑把该模式拆成独立 G02/G03。
- 若需要自动回传交互结果，应先设计 Codex 可用的监听/通知机制，而不是直接复用 Claude Code Monitor 方案。
- 下一轮系统更新时，可同步检查 `B06 normalize.ps1` 对 `.history/AGENTS`、`.history/CLAUDE` 的判断口径，避免与 `workspace-spec.json` 的必备目录定义冲突。

