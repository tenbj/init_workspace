# AI 决策 Schema

AI 只写 JSONL，不直接改 Excel。每行必须是一个 JSON 对象。

## 字段决策

文件：

```text
03_ai_decisions/ai_field_review_decisions.jsonl
```

字段：

| 字段 | 必填 | 说明 |
|---|---|---|
| `sheet_name` | 是 | 来源实体 sheet |
| `row_number` | 是 | 原 Excel 行号 |
| `current_field_name` | 是 | 当前字段名，可为空字符串 |
| `recommended_field_name` | 是 | 推荐字段名，可为空字符串 |
| `decision` | 是 | 决策枚举 |
| `confidence` | 是 | `high` / `medium` / `low` |
| `reason` | 是 | AI 判断依据 |
| `human_question` | 否 | 需要人确认时填写 |
| `writeback_allowed` | 是 | 第一版通常为 `false` |

决策枚举：

| 决策 | 含义 |
|---|---|
| `keep` | 当前字段名可保留 |
| `fill_safe` | 字段名为空且高置信度可填 |
| `suggest_with_review` | 有建议，但需要人工确认 |
| `replace_suggestion` | 当前字段名不佳，建议替换 |
| `need_human_confirm` | 信息不足，需要人判断 |
| `cannot_decide` | 无法判断，作为阻断项 |

示例：

```json
{"sheet_name":"管理快报-金额","row_number":5,"current_field_name":"msku_id","recommended_field_name":"msku_id","decision":"keep","confidence":"high","reason":"字段描述为 msku 维表 id，当前字段名与标准词根一致。","human_question":"","writeback_allowed":false}
```

## 表名决策

文件：

```text
03_ai_decisions/ai_table_review_decisions.jsonl
```

字段：

| 字段 | 必填 | 说明 |
|---|---|---|
| `sheet_name` | 是 | 实体 sheet |
| `current_table_name` | 是 | 当前表名 |
| `recommended_table_name` | 是 | 推荐表名 |
| `decision` | 是 | 同字段决策枚举，可用 `keep` / `suggest_with_review` / `need_human_confirm` |
| `confidence` | 是 | `high` / `medium` / `low` |
| `reason` | 是 | 判断依据 |
| `human_question` | 否 | 需要确认的问题 |

## 待沉淀标准

文件：

```text
03_ai_decisions/ai_standard_gaps.jsonl
```

字段：

| 字段 | 必填 | 说明 |
|---|---|---|
| `gap_type` | 是 | `new_word_root` / `semantic_relation` / `alias` / `rule_gap` / `other` |
| `source_sheet` | 是 | 来源 sheet |
| `source_row` | 否 | 来源行号 |
| `field_desc` | 否 | 字段描述 |
| `suggested_standard` | 是 | 建议沉淀的标准 |
| `reason` | 是 | 为什么需要沉淀 |
| `status` | 是 | 默认 `待确认` |

## AI 约束

- 不确定时不要编造标准，写 `need_human_confirm` 或 `cannot_decide`。
- 标准库未覆盖但业务上明显需要复用时，写入 `ai_standard_gaps.jsonl`。
- `writeback_allowed=true` 只用于高置信度、低风险、字段名为空的 `fill_safe`，且第一版仍默认不自动覆盖。
