# SQL 模板库

脚本已自动完成模板填充，本文件供 LLM 后处理时参考标准格式。

---

## 审计字段（固定）

所有表统一使用：

```sql
NOW() as first_inserted_dt,
NOW() as etl_dt,
NOW() as last_updated_dt
```

---

## 字段加工规则（脚本处理范围）

### FIELD-002：字段名修正

ODS 字段名为驼峰或紧凑命名 → 转 snake_case，值不变。

```sql
-- 原：src.campaignId
-- 改：src.campaignId as campaign_id
```

### FIELD-006：毫秒时间戳修正

字段名含 `_time`/`_at`/`_ts` 且疑似 13 位整数时：

```sql
from_unixtime(src.<field> / 1000) as <field_snake>
```

### FIELD-007：枚举字段（LLM 处理）

先区分编码与描述。若上游表达式或数仓查询已证明源值为业务描述，直接以 `*_desc` 别名输出并记录证据；下列 NULL 模板仅用于缺少确认映射的枚举编码。

脚本在配套开发说明.md记录枚举候选字段；LLM在同一说明中补充判断和处理结论，保留告警来源。SQL不添加文件头注释。

枚举字段后新增 `_desc` 列，`NULL` 占位必须带行内人工确认注释：

```sql
src.status,
NULL as status_desc, -- TODO_CONFIRM: 补充 status 中文映射后替换 NULL
```

目标字段列表同步新增 `status_desc`。

字段命名后必须二次扫描最终 INSERT 字段名；如果紧凑字段（如 `settlementstatus`）被重命名为 `settlement_status`，仍需按枚举字段处理，不能只依赖配套说明中的脚本候选清单。

### COMMENT-001：人工确认点注释

脚本告警和LLM处理结果保留在配套开发说明.md中，不作为SQL头注释。对未命中维表的情况记录告警来源、补充关联依据与待确认条件。

凡需要人工确认的 SQL 位置，也必须就地标注：

```sql
-- TODO_CONFIRM: 该 dim_shop 关联来自历史确认资料，请确认 shopname + sitename 及过滤条件仍适用
left join (
    select acc_name, country, shop_id
    from glcd.dim_shop_ich_dd
    where is_valid = 1
) dim_shop
    on src.shopname = dim_shop.acc_name
   and src.sitename = dim_shop.country
```

所有 `TODO_CONFIRM` 必须同步写入同目录 `.md` 的「待处理」项。

---

## 脚本无法直接生成的情况

遇到以下情况，脚本可能退出或生成不完整初稿；按 `AI接续解析.md` 由 AI 核实并接续，不把脚本限制视为任务失败：

- 找不到 ODS SQL 文件
- ODS SQL 含 `LATERAL VIEW`、`EXPLODE`
- ODS SQL 主查询含 `GROUP BY`、`DISTINCT`
- `INSERT` 目标列数与 `SELECT` 列数不一致

区分上游抽取与本次 DWD 清洗的层级。只有实际要求改变 ODS 到 DWD 粒度或必要证据确实缺失时，才报告不能满足一对一的具体原因。
