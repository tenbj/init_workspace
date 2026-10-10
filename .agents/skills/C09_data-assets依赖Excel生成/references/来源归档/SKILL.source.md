---
name: C09_data-assets依赖Excel生成
description: 当用户需要扫描 data-assets 脚本并生成表上下游依赖 Excel 时使用；同步仓库、解析血缘并输出工作簿。
---

# C09_data-assets依赖Excel生成

## 这项技能解决什么问题

- 将 `data-assets` 仓库同步到远端 `master` 后，静态解析 SQL/Python 脚本中的数据表和直接上下游依赖。
- 输出包含文件清单、数据表清单、上下游依赖明细、外部上游引用和异常清单的 Excel。

## 先读哪些本地知识

- 若需要同步仓库的风险边界，先读 `C01`。
- 若输出到 `output/` 正式子项目，写入前执行 `B02`；任务较长时执行 `B08`。
- 需要理解表识别、依赖解析和异常口径时，再读 `references/生成口径.md`。

## 固定动作

1. 定位目标 `data-assets` 仓库；默认使用 `input/12_数据开发工作台/repos/data-assets`。
2. 默认同步到远端 `master`，并禁用 `origin` push 地址。
3. 运行 `scripts/generate_data_assets_dependency_excel.py` 生成 Excel，并检查终端统计和 workbook sheet 行数。

## 什么时候再读本 skill 的 references

- 需要调整扫描范围、输出路径、是否跳过同步、是否包含未 tracked 文件时，读 `references/使用说明.md`。
- 需要解释“是否数据表”、库名推断、多目标脚本、外部上游和异常清单时，读 `references/生成口径.md`。

## 边界

- 不执行 SQL/Python 业务脚本，只做静态解析。
- 不把无法解析到仓库内表清单的 `from/join` 引用计入上下游数量；这类引用进入外部上游明细。
- 不对 `data-assets` 执行 push、merge 或 rebase。
