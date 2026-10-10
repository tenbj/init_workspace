---
name: E04_模型设计运行归档
description: 当用户需要以归档方式运行 E03 模型命名建议时使用；准备 run 目录、归档输入并交付路径上下文。
---
# 模型设计运行归档

## 这项技能解决什么问题

当用户主动要求归档式运行 E03 时，将指定输入、AI 决策、交付文件和状态保存在一个 run 内。直接调用 E03 不自动开启本归档流程。

## 先读哪些本地知识

- 先读 `references/本地适配说明.md` 与 `references/运行归档契约.md`。
- 按注册表读取当前 E03。命名判断、JSON 结构、质量门与输出能力均以当前注册版本为准。
- 按 B04 定位或创建 `output/` 下模型设计标准化子项目；修改已有产物按 B02。

## 固定动作

1. 确认标准库、模型设计 Excel、run 名称及已有目标子项目；不归档用户未指定的输入。
2. 运行 `scripts/model_run_archive.py prepare`，显式传 `--project-dir`。通常使用 `--archive-mode copy`；只有用户要求移动输入时才使用 move 或 move-or-copy。
3. 用 prepare 返回的 effective path 调用 E03 extract，把上下文存入 run。按当前 E03 规范由 AI 生成 recommendations JSON。
4. 调用当前 E03 write，传 `--model`、`--recommendations`、`--output`、归档后的 `--standard-lib`，并将 `--quality-report` 指向run内。标准建议sheet及质量门遵循当前E03合同。
5. 核对Excel和质量报告均存在后，将两者作为deliverable登记，再 finalize completed；失败则 finalize failed，记录原因并保留输入与上下文。
6. 按 B03/B08 收尾，交付 Excel、run_summary.md 和关键路径。

## 什么时候再读本 skill 的 references

目录、CLI、输入存放与失败恢复见 `references/运行归档契约.md`；来源新版行为仅在 `references/来源归档/` 中追溯。

## 边界

- 不升级 E03、不代替 E03 生成命名建议，不编排 E01/E02。
- 全部运行产物落在目标子项目的 `03_代码程序/runs/`；不新建带版本后缀的 live 目录。
- 子项目不存在时停止并按 B04 创建，不由归档脚本直接重写知识地图。
- 归档后只用 effective path，保留旧 run，不覆盖同名输出。
