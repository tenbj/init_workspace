---
name: E01_模型设计标准化
description: 当用户需要将模型设计 Excel 按标准库进行 AI-first 标准化评审时使用，解析输入、生成 AI 工作包、校验决策并输出建议版 Excel 与评审清单。
metadata:
  short-description: 标准库 + 模型设计 Excel -> AI 字段建议与评审清单
---

# 模型设计标准化

## 这项技能解决什么问题

将模型设计 Excel 与标准库 Excel 转成可审计的运行目录，由脚本完成解析、批次生成、AI 决策校验、评审版 Excel/CSV/摘要输出；必要时可生成模板回填版 Excel，原位维护目录页和实体设计 sheet。语义判断由 AI 全量执行，不维护脚本规则库。

适用于字段名为空、字段名待规范、表名待评审、标准库覆盖不足、需要形成待人工确认和待沉淀标准清单的模型设计文档。

## 先读哪些本地知识

- 输入约定和参数：`references/input_contract.md`
- AI 决策 JSONL 结构：`references/ai_decision_schema.md`
- 输出目录和交付物：`references/output_artifacts.md`
- Excel 模板识别口径：`references/excel_template_contract.md`

## 固定动作

收到模型设计标准化任务后，按下面顺序执行：

1. 确认输入路径。标准库默认 `input/标准库.xlsx`；模型设计 Excel 由用户指定；样例设计和 `data-assets` 可选。
2. 判断输出位置。正式写入 `output/` 前，先按话题归属定位当前 `模型设计标准化` 子项目；不存在时执行 B04 创建，禁止假设子项目编号固定。
3. 正式写入 `output/` 前，执行 B02 对当前 `模型设计标准化` 子项目做 PROJECT 备份；临时试跑可显式传入 `.temp/...` 作为 `--run-dir`。
4. 运行 `scripts/01_parse_workbooks.py`，生成 run 目录、输入清单、Excel 解析产物、模板检查结果、字段 JSONL、标准库原文 JSON 和 `workbook_layout.json`（sheet 顺序/隐藏状态/合并单元格/行列尺寸/字体样式摘要等）。
5. 运行 `scripts/02_build_ai_batches.py`，按实体 sheet 生成 AI 工作包和 AI 决策模板；生成批次前必须解析并应用字段级控制标识：
   - `是否保留=否` 的字段不进入 AI 评审。
   - `是否删除=是` 的字段不进入 AI 评审。
   - 跳过字段写入 `02_ai_batches/skipped_fields.jsonl`，保留 sheet、行号、字段名和跳过原因，便于审计。
   - `是否为枚举字段` 必须作为 Excel 权威标识传入 AI 工作包；标识有值时，AI 不得自行反向猜测该字段是否枚举。
6. AI 读取 `02_ai_batches/ai_field_review_batches.jsonl`，全量评审字段和表名，写入：
   - `03_ai_decisions/ai_field_review_decisions.jsonl`
   - `03_ai_decisions/ai_table_review_decisions.jsonl`
   - `03_ai_decisions/ai_standard_gaps.jsonl`
7. 运行 `scripts/03_validate_ai_decisions.py`，只做客观校验，不做语义判断。
8. 运行 `scripts/04_writeback_excel.py`，默认 `review_only`，复制原模型设计 Excel 并新增评审 sheet，不覆盖原字段名；如用户要求按模型设计模板交付，使用 `--mode template_writeback`：先创建与原 Excel hash 一致的 `{原文件名}_待标准化.xlsx` 副本，再复制为 `{原文件名}_已标准化.xlsx` 并在该文件中原位维护 `1.1 模型设计目录` 的模型跳转/实体表名，将高置信字段决策写回实体 sheet 的 `字段名` 列。`已标准化` workbook 保留原 sheet、隐藏状态、合并单元格和样式，并新增 `0 标准化结果` sheet 作为中文留痕清单；清单中的“单元格”列可点击跳转到原实体 sheet 的具体单元格；表名、字段名本身按标准化结果保留英文标识。
9. 运行 `scripts/05_generate_run_summary.py`，刷新根目录和交付目录下的运行摘要。
10. 向用户报告 `run_summary.md` 和 `06_deliverables/` 下最终文件路径。

## 什么时候再读本 skill 的 references

- 不确定命令参数、run 目录策略、输入文件缺省值时，读 `references/input_contract.md`。
- 需要 AI 生成或修复决策 JSONL 时，读 `references/ai_decision_schema.md`。
- 需要解释中间产物和最终交付物时，读 `references/output_artifacts.md`。
- 模板识别失败、字段列找不到、sheet 类型异常时，读 `references/excel_template_contract.md`。

## 边界

- 脚本不维护候选集合、弱证据规则、token 抽取规则或字段语义判定策略。
- 脚本不判断“商品是否等于 MSKU”这类业务语义，只把上下文完整交给 AI。
- 默认 `review_only`，不得静默覆盖原模型设计字段名；`template_writeback` 只能写入 AI 决策中高置信、可自动落地的字段名/表名，不确定项必须进入评审清单。
- 字段无法匹配标准库时，不静默跳过；AI 应写入人工确认或待沉淀标准。
- 不把一次运行的中间产物只放在对话上下文里，必须落盘到 `runs/{run_id}/`。
- 不把 `模型设计标准化` 子项目编号写死为 `01`；正式输出必须由 B04/SSOT 子项目体系定位当前 live 目录。
