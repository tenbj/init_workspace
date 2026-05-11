# 商品与 MSKU 语义关系中脚本和 AI 协作边界

> 本文专门解释“商品”和“MSKU”这类语义关系在模型设计标准化中的处理方式。  
> 核心结论：脚本负责收集证据和生成关系任务，AI 负责上下文语义判断，人和标准库负责最终标准确认。

---

## 1. 先给结论

“商品”和“MSKU”不能被系统全局默认成一回事。

它们可能在某些上下文里等价，例如利润核算模型以“店铺 + MSKU + 日期”为粒度时，业务口语里的“商品”常常实际指 MSKU。但在其他上下文里，“商品”可能指：

- SPU 或产品主数据。
- SKU。
- MSKU。
- ASIN。
- FNSKU。
- Listing。
- 商品类目或商品组。

所以这类关系不能靠脚本直接判断，也不能让 AI 一句话拍死。正确做法是：

```text
脚本收集证据 -> AI 判断当前上下文里的语义关系 -> 输出置信度和待确认点 -> 用户确认后沉淀为标准或上下文规则
```

---

## 2. 脚本能做什么

脚本没有业务理解能力。它不能“知道商品就是 MSKU”。但它非常适合做证据收集。

### 2.1 收集当前字段上下文

对于一行字段设计，脚本可以抽取：

```json
{
  "sheet_name": "管理快报-金额",
  "table_name": "cbebg.dmt_profit_snapshot_amt_ilu_dd",
  "field_desc": "商品ID",
  "field_name": "",
  "reference_field": "msku_id",
  "reference_table": "cbebg.dws_fin_settlement_shop_msku_subject_ilu_dd",
  "field_category": "主数据",
  "business_keys": ["shop_id", "msku_id", "biz_date"],
  "model_topic": "利润核算",
  "layer": "DMT"
}
```

这些信息本身不等于结论，但能构成 AI 判断所需的证据包。

### 2.2 收集标准库证据

脚本可以查：

- 标准库里是否有“商品”。
- 标准库里是否有“产品”。
- 标准库里是否有“SKU/MSKU/ASIN/FNSKU”。
- 这些词根的标准英文是什么。
- 是否存在已定义的同义词或上下位关系。

脚本能输出：

```json
{
  "standard_hits": [
    {"chinese_name": "商品", "root": "prd", "source": "standard_library"},
    {"chinese_name": "MSKU", "root": "msku", "source": "standard_library"}
  ],
  "standard_conflicts": [
    "字段描述命中“商品”，参考字段命中“msku_id”，两者标准词根不同"
  ]
}
```

脚本不能输出：

```text
商品 = MSKU
```

它最多能说：

```text
商品 和 MSKU 同时被当前字段证据命中，需要语义判断。
```

### 2.3 收集样例模型证据

脚本可以统计完结模型设计文档中类似模式：

| 证据 | 脚本能统计 |
|---|---|
| 字段描述包含“商品”时常见字段名 | `product_id`、`msku_id`、`asin` |
| 字段描述包含“MSKU”时常见字段名 | `msku_id` |
| 参考字段为 `msku_id` 时目标字段名 | 多数保留为 `msku_id` |
| 业务主键里是否经常出现 `shop_id + msku_id + biz_date` | 可以统计 |
| 表名里是否含 `msku` | 可以统计 |

脚本能得出：

```json
{
  "sample_evidence": [
    {
      "pattern": "profit models use shop_id + msku_id + date as grain",
      "support_count": 6
    },
    {
      "pattern": "field_desc contains 商品 but reference_field is msku_id",
      "support_count": 2
    }
  ]
}
```

但它仍然不能断言“商品就是 MSKU”。统计共现不是语义等价。

### 2.4 收集依赖图证据

如果已经把依赖流转成图，脚本可以查：

- 当前模型上游是否是 MSKU 粒度模型。
- 上游表名是否含 `msku`。
- 当前模型业务主键是否含 `msku_id`。
- 是否存在产品维表或 MSKU 维表节点。
- 当前字段来自哪条依赖边。

例如：

```json
{
  "graph_evidence": {
    "upstream_models": [
      "cbebg.dws_fin_settlement_shop_msku_subject_ilu_dd"
    ],
    "grain_fields": ["shop_id", "msku_id", "biz_date"],
    "dependency_path": [
      "领星结算报告映射结果",
      "领星结算报告-店铺MSKU科目汇总",
      "管理快报-金额"
    ]
  }
}
```

这说明当前模型在 MSKU 粒度上工作，但是否把“商品”字段命名为 `msku_id` 仍要 AI 判断。

### 2.5 生成语义关系任务

脚本最终应该生成一个任务，而不是生成结论。

文件可命名为：

```text
semantic_relation_tasks.jsonl
```

一行一个任务：

```json
{
  "task_id": "semantic:管理快报-金额:R5:商品ID",
  "question": "字段描述“商品ID”在当前上下文是否应使用 msku_id？",
  "terms": ["商品", "MSKU"],
  "field_context": {
    "field_desc": "商品ID",
    "reference_field": "msku_id",
    "reference_table": "cbebg.dws_fin_settlement_shop_msku_subject_ilu_dd",
    "business_keys": ["shop_id", "msku_id", "biz_date"],
    "model_topic": "利润核算"
  },
  "evidence": {
    "standard_hits": [],
    "sample_evidence": [],
    "graph_evidence": {}
  }
}
```

这就是脚本和 AI 的接口。

---

## 3. AI 能做什么

AI 的价值是做上下文语义判断，但 AI 的判断也不能直接等于企业标准。

### 3.1 AI 判断关系类型

AI 应该把“商品”和“MSKU”的关系分成明确类型，而不是只说“是”或“不是”。

建议关系类型：

| 关系类型 | 含义 | 示例 |
|---|---|---|
| `exact_equivalent` | 在企业标准中就是同义 | 罕见，需标准库已确认 |
| `context_equivalent` | 在当前模型上下文等价 | 利润核算里“商品”实际指 MSKU |
| `broader_than` | A 比 B 更宽 | 商品 比 MSKU 更宽 |
| `narrower_than` | A 比 B 更窄 | MSKU 是商品的一种业务粒度 |
| `source_alias` | 来源系统字段名与标准名映射 | 来源叫 `seller_sku`，标准用 `msku` |
| `ambiguous` | 证据不足，无法判断 | 商品可能是 ASIN 或 MSKU |
| `conflict` | 证据相互冲突 | 描述是商品，参考字段是 ASIN，业务主键是 msku |

对“商品/MSKU”，多数情况下更合理的关系是：

```text
商品 broader_than MSKU
或
商品 context_equivalent MSKU
```

而不是全局：

```text
商品 exact_equivalent MSKU
```

### 3.2 AI 输出结构化裁决

AI 的输出应持久化到：

```text
semantic_relation_decisions.jsonl
```

示例：

```json
{
  "task_id": "semantic:管理快报-金额:R5:商品ID",
  "relationship": "context_equivalent",
  "recommended_field_name": "msku_id",
  "confidence": "medium_high",
  "basis": [
    "参考字段为 msku_id",
    "参考表名包含 shop_msku_subject",
    "当前模型业务主键包含 shop_id、msku_id、biz_date",
    "利润核算快报模型通常以店铺 MSKU 为商品粒度"
  ],
  "risk": [
    "字段描述“商品ID”过宽，可能被理解为产品/SPU/SKU/ASIN",
    "若企业标准中商品不等于 MSKU，则应修改字段描述或补充标准关系"
  ],
  "human_review_question": "请确认本模型中的“商品”是否特指 MSKU 粒度。如果是，建议字段描述改为“MSKU维表ID”或沉淀“利润核算场景下商品=MSKU粒度”的上下文规则。"
}
```

注意：AI 不只是给 `msku_id`，还要说明为什么、风险在哪里、需要人确认什么。

### 3.3 AI 应避免什么

AI 不应该：

- 把上下文等价说成全局等价。
- 在证据不足时给高置信度。
- 用常识覆盖标准库。
- 把“商品”强行统一成一个英文词根。
- 静默修改字段描述。

AI 可以建议：

- 字段名使用 `msku_id`。
- 字段描述从“商品ID”改成“MSKU维表ID”。
- 待沉淀标准里增加“商品/MSKU 关系”。
- 本轮标记为需要人工确认。

---

## 4. 人和标准库负责什么

人负责确认“关系是否成为标准”。AI 只能提出建议。

### 4.1 人需要确认的事项

对于“商品/MSKU”，用户需要确认：

1. 在利润核算主题下，“商品”是否默认指 MSKU？
2. 在所有主题下，“商品”是否都可以指 MSKU？
3. 标准库中应该保留“商品”作为宽泛概念，还是明确拆成产品、SKU、MSKU、ASIN、FNSKU？
4. 字段描述是否允许写“商品ID”，还是必须写“MSKU维表ID”？
5. 如果业务人员口语说商品，但模型字段必须叫 MSKU，是否要在标准库里维护别名关系？

### 4.2 标准库应沉淀什么

不建议沉淀：

```text
商品 = MSKU
```

建议沉淀更精确的关系：

```json
{
  "relation_type": "context_equivalent",
  "term_a": "商品",
  "term_b": "MSKU",
  "context": {
    "business_domain": "财务域",
    "project": "利润核算",
    "grain": ["shop_id", "msku_id", "biz_date"]
  },
  "preferred_field_root": "msku",
  "preferred_id_field": "msku_id",
  "description_rule": "当模型粒度为店铺+MSKU时，业务口语“商品”应标准化描述为 MSKU 或店铺商品粒度。",
  "status": "待确认"
}
```

也就是说，标准库不只存词根，还应该逐步扩展出“语义关系表”。

---

## 5. 推荐增加一个语义关系库

仅靠“映射标准库”不够，因为映射标准库更像词典。商品/MSKU 这种是语义关系，不是单词翻译。

建议后续标准库新增一个 sheet：

```text
语义关系标准库
```

字段建议：

| 字段 | 说明 |
|---|---|
| 关系ID | 唯一编号 |
| 术语A | 如 商品 |
| 术语B | 如 MSKU |
| 关系类型 | exact_equivalent/context_equivalent/broader_than/narrower_than/source_alias |
| 适用业务域 | 如 财务域 |
| 适用主题 | 如 利润核算 |
| 适用粒度 | 如 店铺+MSKU+日期 |
| 推荐字段名 | 如 msku_id |
| 推荐字段描述 | 如 MSKU维表ID |
| 反例或禁用场景 | 如 商品主数据、SPU分析、ASIN分析 |
| 状态 | 生效/待确认/废弃 |
| 备注 | 人工说明 |

这样脚本才能检索到“已确认的语义关系”，AI 才能有标准依据。

---

## 6. 商品/MSKU 的完整处理流程

### 6.1 第一步：脚本发现可疑关系

触发条件：

- 字段描述含“商品”，参考字段含 `msku`。
- 字段描述含“产品”，参考字段含 `msku`。
- 模型主键含 `msku_id`，字段描述却写“商品”。
- 表名含 `msku`，字段描述却写“商品”。
- 标准库命中多个候选：商品、产品、MSKU、SKU。

脚本输出：

```text
这是一个需要语义判断的字段。
```

### 6.2 第二步：脚本打包证据

证据包括：

- 当前字段行。
- 模型目录。
- 依赖图路径。
- 业务主键。
- 标准库命中项。
- 样例模型统计。
- 代码证据。

### 6.3 第三步：AI 判断关系类型

AI 判断：

- 当前“商品”是否只是口语表达。
- 参考字段是否比描述更可信。
- 模型粒度是否支持 MSKU。
- 是否存在 ASIN/SKU/Product 等竞争候选。
- 是否需要人确认。

### 6.4 第四步：AI 给字段建议

可能输出：

| 情况 | 字段名建议 | 备注 |
|---|---|---|
| 证据强，当前粒度明确是 MSKU | `msku_id` | 字段描述建议改为“MSKU维表ID” |
| 证据中等，商品可能指 MSKU | `msku_id` | 标记待确认 |
| 证据冲突，商品也可能是 ASIN | 不自动填 | 进入阻断评审 |
| 标准库已有上下文关系 | 按标准库 | 高置信度 |

### 6.5 第五步：进入待沉淀清单

如果标准库没有这类关系，应写入 `待沉淀标准` sheet：

| 缺口类型 | 术语A | 术语B | 建议关系 | 适用上下文 | 推荐字段名 | AI 理由 | 用户意见 |
|---|---|---|---|---|---|---|---|
| 语义关系 | 商品 | MSKU | context_equivalent | 财务域/利润核算/店铺+MSKU+日期 | msku_id | 参考字段、参考表、模型粒度均指向 MSKU |  |

用户确认后，才进入语义关系标准库。

---

## 7. 边界总结

### 7.1 脚本边界

脚本可以：

- 查标准库。
- 查样例。
- 查依赖图。
- 查代码。
- 统计共现。
- 发现冲突。
- 生成语义任务。
- 按 AI 决策回写。

脚本不可以：

- 断言商品等于 MSKU。
- 判断业务口语。
- 替企业制定标准。
- 在语义冲突时自动拍板。

### 7.2 AI 边界

AI 可以：

- 基于证据判断当前上下文关系。
- 给推荐字段名。
- 说明依据、风险、置信度。
- 生成待确认问题。
- 提出标准沉淀建议。

AI 不可以：

- 把建议当成已生效标准。
- 在无证据时高置信度生成。
- 静默改标准库。
- 全局定义商品等于 MSKU。

### 7.3 用户和标准库边界

用户和标准库负责：

- 确认企业级术语关系。
- 决定哪些上下文规则生效。
- 决定字段描述是否需要规范化。
- 决定标准库是否新增“语义关系标准库”。

---

## 8. 最小可执行实现

第一版不需要一上来解决所有语义关系。可以先做最小闭环：

1. 脚本发现字段描述和参考字段存在词根冲突。
2. 生成 `semantic_relation_tasks.jsonl`。
3. AI 对每个任务输出 `semantic_relation_decisions.jsonl`。
4. 高置信度建议用于字段名候选。
5. 中低置信度进入 `待沉淀标准` sheet。
6. 用户确认后，下一轮再把确认结果转成语义关系标准。

这样，“商品/MSKU”不是被硬编码进系统，而是通过一次次模型设计评审沉淀成可复用标准。

---

## 9. 对当前问题的直接解释

如果遇到字段：

```text
字段描述：商品ID
参考字段：msku_id
参考库表：cbebg.dws_fin_settlement_shop_msku_subject_ilu_dd
业务主键：shop_id + msku_id + biz_date
模型主题：利润核算
```

脚本会说：

```text
字段描述命中“商品”，参考字段和模型粒度命中“MSKU”，存在语义关系待判断。
```

AI 会说：

```text
在当前利润核算模型中，“商品ID”大概率指 MSKU 粒度，推荐字段名 msku_id。
但“商品”是宽泛词，不应全局等同 MSKU。建议将字段描述规范为“MSKU维表ID”，并把“利润核算/店铺+MSKU粒度下商品口语指 MSKU”写入待沉淀标准，由用户确认。
```

用户确认后，系统才把这条关系变成标准化规则。这个边界是最重要的。
