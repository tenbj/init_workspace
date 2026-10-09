---
name: B11_Git分支工作流
description: 当用户需要在Git仓库中修改文件、提交改动或管理分支验收时使用；识别真实仓库，保护基线，按授权验证、提交、推送和合并。
---
# B11_Git分支工作流 · WorkBuddy 桥接壳

本壳将调用转交给 `.agents/skills/B11_Git分支工作流/SKILL.md`，不复制源技能的执行逻辑。

1. 读取工作区 `AGENTS.md`，遵守其中的 SSOT 顺序、授权边界和当前有效规则；桥接不额外授予权限。
2. 读取 `.agents/skills/B11_Git分支工作流/SKILL.md` 并按原技能的触发条件、步骤和边界执行。
3. 原技能引用的 `scripts/`、`references/`、`assets/` 等相对路径，以 `.agents/skills/B11_Git分支工作流/` 为基准；不得在本桥接目录中查找。脚本工作目录和参数按原技能说明设置。
4. 通过稳定编号调用其他技能时，按 `Skills管理标准.md` 的路由从当前注册表唯一解析；目标缺失或不唯一时报告，不猜旧路径。
5. 输出、备份与记忆按源技能和当前工作区规则执行；记忆由 B03 按 PROJECT / SYSTEM / BOTH 路由，不统一强制写入子项目对话记录。
6. PowerShell 读取项目文本显式使用 `Get-Content -LiteralPath <path> -Encoding UTF8 -Raw`；修改 `.ps1` 时遵守源技能和工作区 BOM 约定。

源技能目录：`.agents/skills/B11_Git分支工作流/`。本目录仅提供桥接入口。
