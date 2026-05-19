---
name: B01_框架体检
description: 会话开始或批量修改后使用；只读检查 SSOT、目录、记忆、历史、编码与 Skill 命名合约。
---

# 框架体检

## 这项技能解决什么问题

在会话开始时或框架批量修改后，快速检查框架健康指标，发现问题后先修再干活。只报问题，不自动修复。

## 何时使用此技能

**会话开始时**：用户提出第一个任务之前，先跑一次体检。
**批量修改后**：修改了多个 Rule/Skill/子项目之后，确认没有引入新问题。

## 固定动作

1. 执行 `scripts/framework-check.ps1`
2. 若所有项 PASS → 继续干活
3. 若有 FAIL → 先修复红色项，再继续干活；WARN 可稍后处理

```powershell
powershell -ExecutionPolicy Bypass -File ".agents\skills\B01_框架体检\scripts\framework-check.ps1"
```

## 检查项目

| # | 检查项 | 失败含义 |
|---|--------|---------|
| 1 | SSOT 标准读取 | `.system/standards/workspace-spec.json` 缺失或无法读取时只能用内置降级项 |
| 2 | 必备骨架目录/文件 | `requiredLayer` 中的目录或文件缺失 |
| 3 | 对话记录完整性 | 有子项目缺少对应对话记录文件 |
| 4 | .ps1 BOM 状态 | `bomCheck.files` 中任一脚本丢失 UTF-8 BOM，中文会乱码 |
| 5 | .memory 当前区洁净度 | 不应存在于当前区的 _v* 历史副本 |
| 6 | 知识地图对齐 | 全局知识地图与实际 output/ 文件夹不一致 |
| 7 | input/ 路径污染 | input/ 中可能存在系统治理文档误放 |
| 8 | 子项目三分类结构 | 新结构或空子项目缺少 `01_问题答疑`、`02_课题研究`、`03_代码程序`，或存在旧版 `_v*` live 目录残留 |
| 9 | 内部文件命名 | `01/02` 分类内文件缺少 `{NN}_` 前缀或 `_v{x.y.z}` 文件版本；`03` 按文件夹整体版本管理 |
| 10 | 目录链接格式 | `目录.md` 的 `01_问题答疑` 与 `02_课题研究` 分节中，正式内容行的文件列必须是 Markdown 链接，且链接目标必须存在 |
| 11 | Get-Content 读取编码 | 入口、Rule、Skill、标准或初始化模板中出现读取文本的 `Get-Content` 命令但未显式使用 `-Encoding UTF8` |
| 12 | `.system` 历史更新日志 | `.history/.system/{文件夹}_{时间戳}` 必须在 `.history/.system/更新日志.md` 中有条目，并列出快照内文件 |
| 13 | README 历史目录 | `README.md` 的历史版本必须进入 `.history/README/`，不得散落在 `.history` 根目录 |

## 边界

- 只读，不修改任何文件
- 不自动修复，只报告问题
- 不在 output/ 子项目中产生输出文件
- 退出码 0 = 全绿，退出码 1 = 有红色项
