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
| `01_parse/template_check.json` | 固定模板检查结果 |
| `01_parse/entity_fields.jsonl` | 一行一个字段或字段映射行 |
| `02_ai_batches/ai_field_review_batches.jsonl` | 一行一个实体 sheet 的 AI 工作包 |
| `03_ai_decisions/*.jsonl` | AI 决策 |
| `04_validation/validation_report.json` | 决策文件客观校验 |
| `05_writeback/writeback_log.json` | Excel/CSV 写入日志 |

## 用户交付物

| 路径 | 说明 |
|---|---|
| `06_deliverables/模型设计标准化建议版.xlsx` | 原模型设计副本 + 评审 sheet |
| `06_deliverables/模型设计标准化运行摘要.md` | 给人看的本次运行摘要 |
| `06_deliverables/待人工确认清单.csv` | 待人判断的问题 |
| `06_deliverables/待沉淀标准清单.csv` | 标准库待补充项 |

## 交付原则

- JSON/JSONL 服务机器审计和复跑。
- Excel/CSV 服务人工评审。
- 第一版不覆盖原字段名，只追加评审 sheet。
- 每条建议必须能追溯到原 sheet 和原行号。
