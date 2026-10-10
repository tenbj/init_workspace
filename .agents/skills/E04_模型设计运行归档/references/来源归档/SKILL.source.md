---
name: E04_模型设计运行归档
description: 当用户需要以归档方式运行 E03 模型命名建议时使用；准备 run 目录、归档输入并交付路径上下文。
---
# E04_模型设计运行归档

## 这项技能解决什么问题

- 当用户主动要求以归档方式运行 E03 模型命名建议时，先把标准库和模型设计 Excel 归档进模型设计标准化子项目的唯一 run 目录。
- 为 E03 提供稳定的 effective path、输出路径和 `run_context.json`，避免产物散落在输入目录或对话上下文里。
- 从 v1.1.0 起，E04 调用 E03 写回时必须传入归档后的标准库路径，使交付 Excel 同步包含标准库原表和标准建议沉淀 sheet。
- 从 v1.1.1 起，E04 调用 E03 生成字段推荐时必须传递参考库表层级口径：参考库表名规范化后以 `dwd_` 为前缀的字段以审核为主，推荐字段名尽量和参考字段名一致，只有与标准强规则、标准映射、命名合规性或字段语义冲突时重新设计；参考库表名不以 `dwd_` 为前缀时，不参考原参考字段名，完全按标准库和字段语义推荐。
- 从 v1.1.2 起，E04 调用 E03 时必须传递同 Excel 字段一致性口径：优先按 `字段名/current_field_name` 复用本 Excel 已有 `推荐字段名`，`字段名` 相同则推荐必须一致；这里的 `字段名` 不是 `参考字段`。
- E04 是 E03 的可选归档入口；用户直接调用 E03 时，仍按 E03 的轻量模式执行。

## 先读哪些本地知识

- 先确认用户给出的标准库 Excel、模型设计 Excel、本次 run 名称，以及目标 `output/` 子项目（如已给出）。
- 未显式给出目标子项目时，先在 `output/` 下自动定位名称包含 `模型设计标准化` 的子项目；子项目名可带或不带版本号后缀；找不到时由 E04 自行创建 `output/{NN}_模型设计标准化`，根子项目名不得带版本号后缀。
- 用户显式给出的目标子项目路径不存在时，不得改写到 `input/`、`.temp/` 或其他位置；只允许在当前工作区 `output/` 下创建或定位模型设计标准化子项目，E04 自行创建时不得加版本号后缀。
- E04 运行产物只允许写入目标 `output/` 子项目的 run 目录；不要把 prepare 结果、中间 JSON 或交付物写到工作区其他区域。
- 需要目录协议、CLI 参数、上下文 JSON 或异常处理细节时，再读 `references/运行归档契约.md`。

## 固定动作

1. 确认标准库 Excel、模型设计 Excel、run 名称和目标 `output/` 子项目。
2. 定位 `output/` 下模型设计标准化相关子项目；名称可带或不带版本号后缀；不存在时自行创建无版本号后缀的标准子项目，不创建到其他路径。
3. 运行 `scripts/model_run_archive.py prepare`，创建唯一 run 目录，归档输入文件，生成 `input_manifest.json`、`run_context.json` 和 run 内 prepare 结果。
4. 使用 prepare 结果中的 effective path 调用 E03：先 extract 到 `run_context.paths.context_json`，再按 E03 的“同字段名一致性优先 -> DWD 参考字段 -> 标准库和语义推荐”流程由 AI 生成 `recommendations_json`，最后携带 `standard_library_path` write 到 `deliverable_excel`。
5. 运行 `scripts/model_run_archive.py finalize`，刷新 run 状态、交付物清单和 `run_summary.md`。
6. 只向用户返回 `run_summary.md`、推荐版 Excel 和关键 run 路径。

## 什么时候再读本 skill 的 references

- 需要确认 `prepare`/`finalize` 参数、run 目录结构、归档移动/复制规则、`run_context.json` 字段或失败恢复策略时，读 `references/运行归档契约.md`。

## 边界

- 不生成字段名或表名建议本身；命名建议仍由 E03 和 AI 决策完成。
- 不编排 E01/E02，不维护标准缺口清单，不把 E04 变成通用运行框架。
- 不让 E03 直接调用时自动切换到 E04，不移动或复制用户未指定归档的输入。
- E04 调用链中不得在归档后继续使用原始 `input/` 路径，不覆盖已有 run 目录或同名输出。
- E04 的运行文件、上下文文件和交付文件只落在目标 `output/` 子项目内。
