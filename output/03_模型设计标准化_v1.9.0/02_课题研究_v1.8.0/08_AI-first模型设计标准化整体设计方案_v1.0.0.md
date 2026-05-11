# AI-first 模型设计标准化整体设计方案

> 本方案基于最新共识：不维护候选集合、弱证据规则、token 抽取规则和脚本判定策略。  
> 因此整体架构采用 AI-first：脚本只做基础设施，AI 做全量语义评审，用户做最终确认。

---

## 1. 总体结论

当前阶段建议只做 **1 个主 Skill**：

```text
E01_模型设计标准化_v1.0.0
```

不要拆成多个 Skill。

原因：

1. 用户入口应简单，只需要一句“处理这个模型设计 Excel”。
2. 当前不维护复杂规则库，多 Skill 之间没有稳定的规则边界。
3. 语义判断由 AI 全量完成，拆分多个 Skill 反而会增加上下文传递成本。
4. 第一版重点是跑通端到端闭环：解析、AI 评审、输出评审清单、Excel 回写。
5. 等流程稳定后，再根据复用性拆分。

内部可以拆成多个脚本，但对用户只暴露一个 Skill。

---

## 2. 一个 Skill 的职责边界

### 2.1 Skill 做什么

`E01_模型设计标准化` 负责端到端执行：

```text
输入标准库 Excel + 模型设计 Excel
  -> 解析 Excel
  -> 固定模板检查
  -> 构造 AI 工作包
  -> AI 全量字段/表名评审
  -> 脚本后验校验
  -> 输出评审清单和待沉淀标准
  -> 可选回写标准化 Excel
```

### 2.2 Skill 不做什么

不做：

- 不要求维护候选集合。
- 不要求维护弱证据规则。
- 不要求维护 token 抽取规则。
- 不用脚本判断字段是否可疑。
- 不让脚本判断字段业务语义。
- 不追求第一版全自动覆盖字段名。

---

## 3. Skill 目录怎么落

建议新建：

```text
.agents/skills/E01_模型设计标准化_v1.0.0/
  SKILL.md
  scripts/
    01_parse_workbooks.py
    02_build_ai_batches.py
    03_validate_ai_decisions.py
    04_writeback_excel.py
    05_generate_run_summary.py
  references/
    input_contract.md
    ai_decision_schema.md
    output_artifacts.md
    excel_template_contract.md
  assets/
    review_sheet_template.xlsx
```

说明：

- `SKILL.md` 只写薄流程和调用顺序。
- 复杂说明放 `references/`。
- 可执行逻辑放 `scripts/`。
- Excel 辅助模板放 `assets/`。

---

## 4. 用户如何调用

推荐调用方式：

```text
用 E01_模型设计标准化 处理 input/模型设计 - xxx.xlsx，标准库用 input/标准库.xlsx
```

可选参数：

| 参数 | 默认 | 说明 |
|---|---|---|
| 标准库路径 | `input/标准库.xlsx` | 标准库 Excel |
| 模型设计路径 | 用户指定 | 待处理设计文档 |
| 样例模板路径 | 可选 | 已完结模型设计文档 |
| data-assets 路径 | 可选 | 代码资产目录 |
| 输出模式 | `review_only` | 只出建议，不覆盖原字段名 |
| 是否回写 | 否 | 第一版默认不直接覆盖 |

---

## 5. 运行目录怎么落

每次执行创建一个 run 目录：

```text
output/01_模型设计标准化_v{version}/03_代码程序_v{version}/runs/{run_id}/
```

示例：

```text
output/01_模型设计标准化_v1.8.0/03_代码程序_v1.0.0/runs/20260511_170000_利润核算快报/
```

`run_id`：

```text
YYYYMMDD_HHMMSS_{任务短名}
```

运行目录内保存全部中间产物，保证换会话可恢复。

---

## 6. 脚本模块怎么落

### 6.1 `01_parse_workbooks.py`

职责：

- 读取标准库 Excel。
- 读取模型设计 Excel。
- 读取样例模板 Excel。
- 稳定解析 worksheet XML，避免 Excel 维度误判。
- 输出固定结构 JSON/JSONL。

输出：

```text
00_run_manifest.json
01_workbook_manifest.json
02_template_check.json
03_model_catalog.json
04_dependency_raw.json
05_entity_sheets.jsonl
06_entity_fields.jsonl
07_standard_library_raw.json
```

注意：该脚本不做语义判断。

### 6.2 `02_build_ai_batches.py`

职责：

- 把字段行按实体 sheet 分批。
- 给每批字段补充模型目录、依赖上下文、标准库原文、样例上下文。
- 生成 AI 可直接评审的工作包。

输出：

```text
08_ai_field_review_batches.jsonl
```

一行一个实体 sheet：

```json
{
  "batch_id": "entity:管理快报-金额",
  "model_context": {},
  "standard_library_context": {},
  "fields": []
}
```

注意：它不判断哪些字段可疑，默认全量给 AI。

### 6.3 AI 全量评审

这一步不是脚本，而是 Skill 主流程中由 AI 执行。

AI 输入：

```text
08_ai_field_review_batches.jsonl
```

AI 输出：

```text
09_ai_field_review_decisions.jsonl
10_ai_table_review_decisions.jsonl
11_ai_standard_gaps.jsonl
```

字段决策结构：

```json
{
  "sheet_name": "管理快报-金额",
  "row_number": 4,
  "current_field_name": "",
  "recommended_field_name": "msku_id",
  "decision": "suggest_with_review",
  "confidence": "medium",
  "reason": "字段描述为商品，但当前模型上下文更像店铺MSKU粒度。",
  "human_question": "请确认商品是否特指 MSKU。",
  "writeback_allowed": false
}
```

### 6.4 `03_validate_ai_decisions.py`

职责：

- 校验 AI 输出 JSONL 是否完整。
- 校验字段名格式。
- 校验重复字段名。
- 校验 AI 是否给出理由和置信度。
- 校验 `writeback_allowed=true` 的项是否安全。

输出：

```text
12_validation_report.json
13_review_items.jsonl
```

该脚本只做客观校验，不判断业务语义。

### 6.5 `04_writeback_excel.py`

职责：

- 复制原模型设计 Excel。
- 新增或更新评审 sheet。
- 写入 AI 字段建议。
- 写入待人工确认。
- 写入待沉淀标准。
- 可选写回高置信度字段名。

默认输出模式：

```text
review_only
```

即不覆盖原字段名，只新增建议和评审清单。

输出：

```text
标准化建议版_模型设计.xlsx
```

### 6.6 `05_generate_run_summary.py`

职责：

- 汇总运行结果。
- 生成给用户看的 Markdown 摘要。
- 统计字段数量、AI 建议数量、需确认数量、阻断项数量。

输出：

```text
run_summary.md
```

---

## 7. AI 决策类别

AI 对每个字段输出一种决策：

| 决策 | 含义 | 回写策略 |
|---|---|---|
| `keep` | 现有字段名可保留 | 记录依据，不改字段名 |
| `fill_safe` | 字段名为空且高置信度可填 | 可选回写 |
| `suggest_with_review` | 有建议但需人工确认 | 写入建议列和评审清单 |
| `replace_suggestion` | 现字段名不佳，建议替换 | 不直接替换，进评审 |
| `need_human_confirm` | 信息不足，需要人工确认 | 不写字段名 |
| `cannot_decide` | 无法判断 | 阻断项 |

第一版只允许 `fill_safe` 在显式授权后自动回写，其余都只出建议。

---

## 8. 输出 Excel 怎么落

最终 Excel 建议包含：

1. 原始 sheet：保持不动或仅标注。
2. `AI字段建议` sheet。
3. `待人工确认` sheet。
4. `待沉淀标准` sheet。
5. `运行摘要` sheet。

### 8.1 `AI字段建议`

列：

| 列 | 说明 |
|---|---|
| sheet 名 | 来源实体 sheet |
| 行号 | 原 Excel 行号 |
| 字段描述 | 原字段描述 |
| 当前字段名 | 原字段名 |
| 推荐字段名 | AI 建议 |
| 决策 | keep/fill_safe/suggest_with_review 等 |
| 置信度 | high/medium/low |
| AI 理由 | 推荐依据 |
| 是否允许回写 | true/false |

### 8.2 `待人工确认`

列：

| 列 | 说明 |
|---|---|
| 问题类型 | 字段命名/表名/粒度/标准缺口 |
| 问题描述 | AI 发现的问题 |
| AI 建议 | 推荐处理 |
| 用户意见 | 用户填写 |
| 处理状态 | 待确认/接受/拒绝/需补充 |

### 8.3 `待沉淀标准`

列：

| 列 | 说明 |
|---|---|
| 缺口类型 | 新词根/语义关系/别名/规则缺口 |
| 来源字段 | 原字段 |
| 推荐标准 | AI 建议沉淀 |
| 适用上下文 | 业务域/模型/粒度 |
| AI 理由 | 为什么建议沉淀 |
| 用户意见 | 用户填写 |

---

## 9. 是否需要多个 Skill

### 9.1 当前不需要多个 Skill

当前只需要 1 个：

```text
E01_模型设计标准化_v1.0.0
```

理由：

- 语义都交给 AI，没有可拆的稳定规则边界。
- 用户目标是一个完整工作流，不是多个独立工具。
- 中间 JSON/Excel 产物都服务于同一任务。
- 多 Skill 会增加调用和版本维护成本。

### 9.2 什么时候拆

满足以下条件再拆：

| 拆分条件 | 说明 |
|---|---|
| 某模块被其他流程复用 | 例如 Excel 模板解析也服务 DWD SQL 生成 |
| 输入输出稳定 | JSON schema 不再频繁变 |
| 用户会独立调用 | 例如只想做标准库体检 |
| 执行频率不同 | 例如 data-assets 索引很重，不想每次跑 |
| 风险级别不同 | 回写 Excel 比只读解析风险高 |

### 9.3 未来可能拆成几个

如果未来拆，建议最多 3 个：

1. `E01_模型设计标准化`
   - 主入口，端到端处理模型设计 Excel。

2. `E02_标准库治理`
   - 处理待沉淀标准、标准库冲突、标准库版本升级。

3. `E03_数据资产证据索引`
   - 扫描 data-assets、DDL、SQL，生成代码证据包。

但这是未来方案，不是当前第一版。

---

## 10. 第一版实施顺序

### 第一步：只读原型

目标：

- 解析 Excel。
- 生成 AI 工作包。
- AI 输出字段建议。
- 输出 Markdown/JSONL 评审结果。

不回写 Excel。

验收：

- 能读完整标准库和模型设计。
- 能生成每个实体 sheet 的 AI review batch。
- AI 输出能覆盖所有字段。

### 第二步：评审版 Excel

目标：

- 新增 `AI字段建议`、`待人工确认`、`待沉淀标准` sheet。
- 不覆盖原字段名。

验收：

- 用户可以直接在 Excel 中评审。
- 每条建议可追溯到原 sheet 和行号。

### 第三步：可控回写

目标：

- 用户确认后，对 `fill_safe` 或用户接受项回写字段名。

验收：

- 回写前后有备份。
- 回写记录可追溯。
- 不覆盖需确认项。

---

## 11. 当前方案的取舍

| 维度 | 选择 | 原因 |
|---|---|---|
| Skill 数量 | 1 个 | 降低入口和维护成本 |
| 语义判断 | AI 全量评审 | 不维护规则时，脚本无法可靠预筛 |
| 脚本角色 | 基础设施 | 解析、打包、校验、回写 |
| 标准库角色 | AI 参考资料 | 不转成脚本规则 |
| 输出方式 | 先评审，不自动覆盖 | 控制 AI 风险 |
| 中间产物 | 持久化 JSON/JSONL | 可审计、可恢复 |

---

## 12. 最终建议

第一版只做：

```text
1 个主 Skill：E01_模型设计标准化_v1.0.0
```

内部通过 5 个脚本落地：

```text
01_parse_workbooks.py
02_build_ai_batches.py
03_validate_ai_decisions.py
04_writeback_excel.py
05_generate_run_summary.py
```

第一版目标不是全自动生成完美字段名，而是：

```text
生成一份可审计、可评审、可回写的标准化建议版模型设计文档。
```

这最符合当前约束：不维护复杂规则、依赖 AI 语义理解、用户通过 Excel 完成最终确认。
