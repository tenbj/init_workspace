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

脚本仅标记，LLM 负责判断并处理：

```sql
-- ⚠️ ENUM_FIELDS: status, order_type
-- LLM请为以上字段判断是否需要补充 _desc 列
```

LLM 处理后，保留顶部来源注释，并追加处理结论：

```sql
-- ⚠️ ENUM_FIELDS: status, order_type
-- LLM请为以上字段判断是否需要补充 _desc 列
-- LLM处理结果：已补 status_desc、order_type_desc，当前使用 NULL 占位，需后续补充 CASE WHEN 映射
```

枚举字段后新增 `_desc` 列，`NULL` 占位必须带行内人工确认注释：

```sql
src.status,
NULL as status_desc, -- TODO_CONFIRM: 补充 status 中文映射后替换 NULL
```

目标字段列表同步新增 `status_desc`。

字段命名后必须二次扫描最终 INSERT 字段名；如果紧凑字段（如 `settlementstatus`）被重命名为 `settlement_status`，仍需按枚举字段处理，不能只依赖脚本头部注释。

### COMMENT-001：人工确认点注释

SQL 顶部保留脚本输出的 `⚠️` 注释作为来源追踪，不把它们当成可删除噪音。LLM 后处理必须在对应注释后追加 `LLM处理结果`。

```sql
-- ⚠️  未检测到标准维表触发信号，如需维表关联请人工确认
-- LLM处理结果：根据历史确认资料补充 dim_shop 关联，关联条件和过滤条件需人工复核
```

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

## 不可自动生成的情况

遇到以下情况脚本直接退出，需人工处理：

- 找不到 ODS SQL 文件
- ODS SQL 含 `LATERAL VIEW`、`EXPLODE`
- ODS SQL 主查询含 `GROUP BY`、`DISTINCT`
- `INSERT` 目标列数与 `SELECT` 列数不一致
