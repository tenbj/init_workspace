# SQL 核验模板

核验完成后的正式唯一性配置使用 [唯一性检验模板.sql](../assets/唯一性检验模板.sql)，生成与交付规则见[输出契约](输出契约.md)。该模板保留组内 `cnt`，最终 `quality_value` 统计重复键组数；以下SQL用于核验取证，不替代正式配置文件。

以下历史示例的字符串拼接键只用于解释思路，分隔符或NULL哨兵可能与原值碰撞；最终结论必须按原始字段列表直接GROUP BY复核，不能只凭CONCAT_WS计数确认重复/唯一。计数唯一还须业务语义证据；完整反例应直接单表验证，排除JOIN放大。具体探查规则见[核验流程](核验流程.md)。

## 1. 全表行数

```sql
SELECT COUNT(*) AS row_cnt
FROM <table_name>;
```

## 2. 技术唯一主键核验

```sql
SELECT
    COUNT(*) AS row_cnt,
    COUNT(DISTINCT <technical_key_expr>) AS technical_key_cnt,
    SUM(CASE WHEN <technical_key_field> IS NULL THEN 1 ELSE 0 END) AS null_technical_key_cnt
FROM <table_name>;
```

如果技术主键是多字段组合，`null_technical_key_cnt` 应分别检查每个关键字段。

## 3. 粒度字段组合唯一性核验

```sql
WITH keyed AS (
    SELECT
        CONCAT_WS(
            '|',
            COALESCE(CAST(<grain_field_1> AS STRING), '<NULL>'),
            COALESCE(CAST(<grain_field_2> AS STRING), '<NULL>'),
            COALESCE(CAST(<grain_field_3> AS STRING), '<NULL>')
        ) AS grain_key
    FROM <table_name>
)
SELECT
    COUNT(*) AS row_cnt,
    COUNT(DISTINCT grain_key) AS grain_key_cnt
FROM keyed;
```

判断：

- `row_cnt = grain_key_cnt`：该字段组合在原始 ODS 上唯一。
- `row_cnt != grain_key_cnt`：该字段组合不是业务主键；如果它仍代表业务对象，只能称为粒度字段组合。

## 4. 重复组分析

```sql
WITH keyed AS (
    SELECT
        CONCAT_WS(
            '|',
            COALESCE(CAST(<grain_field_1> AS STRING), '<NULL>'),
            COALESCE(CAST(<grain_field_2> AS STRING), '<NULL>'),
            COALESCE(CAST(<grain_field_3> AS STRING), '<NULL>')
        ) AS grain_key,
        t.*
    FROM <table_name> t
),
dup AS (
    SELECT grain_key
    FROM keyed
    GROUP BY grain_key
    HAVING COUNT(*) > 1
)
SELECT
    COUNT(DISTINCT k.grain_key) AS duplicate_group_cnt,
    COUNT(*) AS duplicate_row_cnt,
    COUNT(*) - COUNT(DISTINCT k.grain_key) AS extra_row_cnt,
    COUNT(DISTINCT <technical_key_field>) AS duplicate_technical_key_cnt
FROM keyed k
JOIN dup d ON k.grain_key = d.grain_key;
```

需要进一步抽样时：

```sql
WITH keyed AS (...),
dup AS (...)
SELECT k.*
FROM keyed k
JOIN dup d ON k.grain_key = d.grain_key
ORDER BY k.grain_key, <order_field_1> DESC, <technical_key_field> DESC
LIMIT 100;
```

## 5. 不含某个争议字段的反证核验

用于判断某字段是否必须进入粒度，例如源端创建时间。

```sql
WITH keyed AS (
    SELECT
        CONCAT_WS(
            '|',
            COALESCE(CAST(<grain_field_without_disputed_field_1> AS STRING), '<NULL>'),
            COALESCE(CAST(<grain_field_without_disputed_field_2> AS STRING), '<NULL>')
        ) AS candidate_key,
        <disputed_field>
    FROM <table_name>
),
dup AS (
    SELECT candidate_key
    FROM keyed
    GROUP BY candidate_key
    HAVING COUNT(*) > 1
)
SELECT
    COUNT(DISTINCT k.candidate_key) AS duplicate_group_cnt,
    COUNT(*) AS duplicate_row_cnt,
    COUNT(DISTINCT k.<disputed_field>) AS disputed_field_distinct_cnt
FROM keyed k
JOIN dup d ON k.candidate_key = d.candidate_key;
```

## 6. 按粒度字段组合取最新

只在用户确认排序字段语义后使用。

```sql
WITH keyed AS (
    SELECT
        CONCAT_WS(
            '|',
            COALESCE(CAST(<grain_field_1> AS STRING), '<NULL>'),
            COALESCE(CAST(<grain_field_2> AS STRING), '<NULL>'),
            COALESCE(CAST(<grain_field_3> AS STRING), '<NULL>')
        ) AS grain_key,
        t.*
    FROM <table_name> t
),
latest AS (
    SELECT
        grain_key,
        ROW_NUMBER() OVER (
            PARTITION BY grain_key
            ORDER BY <collect_update_time> DESC, <source_update_time> DESC, <technical_key_field> DESC
        ) AS rn
    FROM keyed
)
SELECT
    COUNT(*) AS latest_row_cnt,
    COUNT(DISTINCT grain_key) AS latest_grain_key_cnt
FROM latest
WHERE rn = 1;
```

输出时写：

```text
按粒度字段组合取最新后，COUNT(*) = COUNT(DISTINCT grain_key)，可得到当前态唯一记录。
```

不要写：

```text
取最新后的业务主键成立。
```
