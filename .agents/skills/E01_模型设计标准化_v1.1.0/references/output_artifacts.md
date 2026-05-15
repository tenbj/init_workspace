# 输出物说明

每次运行生成一个 run 目录：

```text
runs/{run_id}/
  00_inputs/
  01_parse/
  02_ai_batches/
  03_ai_decisions/
  04_validation/
  05_writeback/
  06_deliverables/
  run_manifest.json
  run_summary.md
```

## 机器产物

| 路径 | 说明 |
|---|---|
| `run_manifest.json` | 本次运行的输入、输出、状态 |
| `01_parse/workbook_manifest.json` | 工作簿、sheet、行列统计 |
| `01_parse/workbook_layout.json` | workbook 布局与样式摘要，包括 sheet 顺序/隐藏状态/合并单元格/行列尺寸/字体样式摘要等 |
| `01_parse/template_check.json` | 固定模板检查结果 |
| `01_parse/entity_fields.jsonl` | 一行一个字段或字段映射行，包含 `is_retained`、`is_deleted`、`is_enum_field` 等 Excel 控制标识 |
| `02_ai_batches/ai_field_review_batches.jsonl` | 一行一个实体 sheet 的 AI 工作包 |
| `02_ai_batches/skipped_fields.jsonl` | 因 `是否保留=否` 或 `是否删除=是` 未进入 AI 评审的字段清单 |
| `03_ai_decisions/*.jsonl` | AI 决策 |
| `04_validation/validation_report.json` | 决策文件客观校验 |
| `05_writeback/writeback_log.json` | Excel/CSV 写入日志 |

## 用户交付物

| 路径 | 说明 |
|---|---|
| `06_deliverables/模型设计标准化建议版.xlsx` | 原模型设计副本 + 评审 sheet |
| `05_writeback/{原文件名}_待标准化.xlsx` | `template_writeback` 模式中创建的原样副本，hash 必须与原模型设计一致 |
| `06_deliverables/{原文件名}_已标准化.xlsx` | `template_writeback` 模式输出；由待标准化副本复制后回填目录页/字段名，保留原 workbook 结构并新增中文 `0 标准化结果` 留痕 sheet |
| `06_deliverables/模型设计标准化运行摘要.md` | 给人看的本次运行摘要 |
| `06_deliverables/待人工确认清单.csv` | 待人判断的问题 |
| `06_deliverables/待沉淀标准清单.csv` | 标准库待补充项 |

## 交付原则

- JSON/JSONL 服务机器审计和复跑。
- Excel/CSV 服务人工评审。
- 默认 `review_only` 不覆盖原字段名，只追加评审 sheet。
- `template_writeback` 用于正式模板交付，只回写高置信可自动落地的字段名和表名；不确定项仍进入待人工确认清单。
- `template_writeback` 的最终 Excel 必须能直接看出改了哪些、没改哪些：新增 `0 标准化结果` sheet，用中文记录对象类型、处理结果、工作表、单元格、原值、标准化后、决策、置信度和说明；“单元格”列必须能点击跳转到原实体 sheet 的具体单元格；被修改的原单元格用浅黄色填充并写入中文批注。
- Excel 中由系统新增的状态、说明、摘要和列名使用中文；表名、字段名作为技术标识不强制汉化。
- 每条建议必须能追溯到原 sheet 和原行号。
