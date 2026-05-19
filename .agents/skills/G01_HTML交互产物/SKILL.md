---
name: G01_HTML交互产物
description: 当用户需要HTML报告、图示、互动编辑器或可视化决策产物时使用；生成单文件HTML并保留原始技能包索引。
---

# G01_HTML交互产物

## 这项技能解决什么问题

- 把外部 `agent-html-skills` 的 16 类 HTML 产物模式收敛为一个项目级薄入口
- 为规格、研究、图示、数据探索、对比矩阵、路线图、ERD、思维导图等任务选择合适 HTML 表达
- 在当前 Codex 工作区中生成可打开、可审阅、可分享的单文件 HTML，而不引入 Claude Code 专属监听依赖

## 先读哪些本地知识

- 先读 `references/HTML产物模式索引.md`，选择最小合适的产物模式
- 需要完整原始规则时，再读 `references/原始技能包/skills/{html-skill}/SKILL.md`
- 需要提交/复制交互结果时，参考 `assets/submit-handler.js` 的剪贴板降级路径
- 需要确认迁入来源与本地化取舍时，再读 `references/迁移说明.md`

## 固定动作

1. 判断用户是否真的需要 HTML 产物；短答、普通代码修改、无需视觉结构的说明不触发。
2. 从模式索引中选择一个主模式，必要时组合一个辅助模式，但不同时展开多个原始 `SKILL.md`。
3. 生成 HTML 时优先单文件、响应式、可离线打开；CSS/JS 内联，避免外部依赖。
4. 互动类产物默认使用剪贴板提交回传；不要要求或假设 Claude Code `Monitor`、`TaskStop` 或本地监听器存在。
5. 若产物属于当前工作区知识输出，仍遵守本项目 `output/`、B02、B03、B08 等本地强制门。

## 什么时候再读 references

- 需要某个模式的完整结构、反模式或示例时，读对应原始 `SKILL.md`
- 需要在相邻模式间分流时，读 `HTML产物模式索引.md` 的“分流规则”
- 需要复核外部仓库信息、提交哈希或本地化改动时，读 `迁移说明.md`

## 边界

- 不把 16 个外部 Skill 全部作为常驻入口注册，避免触发范围和上下文成本失控
- 不启用 `html-skills-listen` / `html-skills-stop` 的 Claude Code 专属服务器模式
- 不用 HTML 产物替代应当直接修改代码、表格、文档或 PowerPoint 的任务
- 不在没有用户需求或明显收益时强行把普通 Markdown 回答改成 HTML
