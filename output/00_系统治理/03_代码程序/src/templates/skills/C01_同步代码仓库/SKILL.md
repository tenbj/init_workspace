---
name: C01_同步代码仓库
description: 当用户需要把 `./input/data-assets` 强制对齐远端 `master`、覆盖本地漂移并禁止 `origin` push 时使用。
---

# C01_同步代码仓库

## 这项技能解决什么问题

- 把 `./input/data-assets` 强制同步到远端 `master`
- 当 `./input/data-assets` 不存在或是空目录时，默认从 `git@git.rabbitgoo.com:dw-dev/data-assets.git` 克隆；也可用 `DATA_ASSETS_REPO_URL` 或 `--clone-url` 覆盖
- 在同步前自动把 `origin` 的 push 地址设置为 `DISABLED`
- 统一使用项目相对路径执行，避免项目移动后脚本路径失效

## 先读哪些本地知识

- 先确认目标仓库就是 `./input/data-assets`
- 需要完整命令、执行顺序、结果判定或异常处理时，再读 `references/同步说明.md`
- 需要核对规范化前的旧版入口说明时，再读 `references/原始技能说明.md`

## 固定动作

1. 只把目标定位到 `./input/data-assets`，不要扩展到别的仓库。
2. 优先运行 `scripts/sync_authoritative_data_assets.py`；只想看当前状态时加 `--status-only`。
3. 目标仓库缺失或目标目录为空时，默认使用 `git@git.rabbitgoo.com:dw-dev/data-assets.git` 克隆；如需切换远端，必须通过 `DATA_ASSETS_REPO_URL` 或 `--clone-url` 显式覆盖。
4. 目标目录已存在但不是 Git 仓库且非空时，停止并报错，不要清理未知内容。
5. 默认接受“远端覆盖本地”的策略，不保留本地冲突、未提交改动或未跟踪文件。
6. 执行后检查 `origin` push 地址、`git status --short --branch` 和最新提交摘要。

## 什么时候再读本 skill 的 references

- 需要复制完整命令时，再读 `references/同步说明.md`
- 需要确认脚本内部执行顺序和风险边界时，再读 `references/同步说明.md`
- 需要比对规范化前的旧入口说明时，再读 `references/原始技能说明.md`

## 边界

- 不要对 `./input/data-assets` 之外的仓库执行这套流程
- 不要执行 `push`、`merge` 或 `rebase`
- 不要把项目相对路径改写成绝对路径
- 不要把长命令、异常细节重新堆回 `SKILL.md`
