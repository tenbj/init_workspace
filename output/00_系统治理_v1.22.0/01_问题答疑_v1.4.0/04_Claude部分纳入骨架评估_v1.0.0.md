# Claude 部分纳入骨架评估

> 日期：2026-05-10  
> 结论：需要更新标准，并同步初始化工具与体检脚本。

---

## 现状识别

当前工作区已经存在 Claude 运行层：

- `CLAUDE.md`：Claude Code 会话入口规则。
- `.claude/settings.local.json`：本机权限设置。
- `.claude/commands/`：15 个 Skill 斜杠命令文件。
- `.Claude.json`：本机环境配置，可能包含密钥。

命令覆盖关系是健康的：`.claude/commands/` 下 15 个命令文件与 `workspace-spec.json` 的 `skillsManagement.registeredSkills` 一一对应，命令正文均指向对应 `.agents/skills/{Skill}/SKILL.md`。

## 标准缺口

原 `workspace-spec.json v1.5.0` 没有把 `.claude/`、`CLAUDE.md`、`.Claude.json`、`.claude/settings.local.json` 纳入根目录、必备层或命令一致性检查，因此体检通过不代表 Claude 接入层被标准保护。

同时，初始化工具模板仍保留旧式无编号中文 Skill 目录，和当前 live 的版本化 Skill 注册表不一致。若不处理，新初始化出来的工作区会重新产生标准漂移。

## 更新方案

本次采用 `workspace-spec.json v1.6.0` 作为新 SSOT：

- 将 `.claude/commands/` 加入必备目录。
- 将 `CLAUDE.md`、`.Claude.json`、`.claude/settings.local.json` 加入必备文件。
- 新增 `claudeIntegration` 配置块，定义命令目录、命令模板、命令来源和私有配置策略。
- 体检脚本新增 Claude 命令覆盖检查。
- 规范化脚本新增 Claude 接入层检查与可修复能力。
- 初始化工具升至 `v2.5.0`，生成 `CLAUDE.md` 与 `.claude/commands/`，并把模板 Skill 同步为当前版本化目录。

## 风险边界

`.Claude.json` 可能包含密钥或模型配置，只能作为本机私有配置识别和补缺占位，不应被模板覆盖，也不应在报告中展示具体值。

---
