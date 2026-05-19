---
name: B08_任务进度管理
description: 当任务需要可恢复的执行进度时使用：创建、更新、恢复、关闭 .memory/任务进度 中的任务状态文件与索引。
---

# B08_任务进度管理

## 这项技能解决什么问题

- 为长任务、系统治理任务和文件修改任务提供可恢复的运行态进度。
- 任务进度只保存“执行到哪一步”的 live 状态，不替代 `output/` 成果文档和 B03 长期记忆。
- 当会话中断、上下文压缩或模型切换时，下一次可以从 `.memory/任务进度/索引.md` 找到恢复入口。

## 先读哪些本地知识

- 先读 `.system/standards/workspace-spec.json`，确认 `.memory/任务进度` 是否已纳入当前标准。
- 涉及记忆收尾时读 `B03`，涉及修改 live 文件前读 `B02`。
- 需要展开状态机、写入时机和脚本参数时，再读 `references/任务进度规则.md`。

## 固定动作

1. 任务开始或恢复时，运行 `scripts/task_progress.ps1 -Action Start` 或 `-Action Resume`。
2. 每个关键状态转移后，运行 `-Action Checkpoint`、`-Action UpdateNext`、`-Action Pause` 或 `-Action Close`。
3. 结束回复前，确认任务状态已写入 `.memory/任务进度/索引.md`；任务完成时关闭并归档。

## 什么时候再读本 skill 的 references

- 不确定何时写 checkpoint、何时暂停、何时关闭任务时，读 `references/任务进度规则.md`。
- 需要人工手动修复索引或理解脚本输出结构时，读 `references/任务进度规则.md`。

## 边界

- 不把最终研究结论、完整方案或长期知识写入任务进度文件。
- 不对 `.memory/任务进度` 做 B02 整目录备份；它是运行态追加记录。
- 不用任务进度替代 B03。任务完成后，只把压缩摘要沉淀到 B03。
