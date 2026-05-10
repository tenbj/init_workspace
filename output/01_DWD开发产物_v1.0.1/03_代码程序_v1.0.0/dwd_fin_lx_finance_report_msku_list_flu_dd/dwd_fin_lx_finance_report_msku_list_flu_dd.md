# 异常说明

## 需人工处理

### 枚举字段（_desc 占位）
以下字段已补充 `_desc` 占位列，当前使用 `NULL`，需后续补充 CASE WHEN 中文映射：
- `transaction_status_desc` → TODO_CONFIRM: 补充 transaction_status 中文映射后替换 NULL
- `transaction_status_code_desc` → TODO_CONFIRM: 补充 transaction_status_code 中文映射后替换 NULL
- `country_code_desc` → TODO_CONFIRM: 补充 country_code 中文映射后替换 NULL
- `currency_code_desc` → TODO_CONFIRM: 补充 currency_code 中文映射后替换 NULL

### 时间戳字段
- `local_created_time` → TODO_CONFIRM: 请核查 ODS 类型，如为 unix 毫秒戳需补充 `from_unixtime(cast(src.local_created_time as bigint) / 1000)` 转换

### 字段命名不确定项
以下字段拆分存在歧义，保留当前拆分结果，需人工确认：
- `cost_of_pointegers_granted` / `cost_of_pointegers_returned`：原字段 `costofpointegersgranted` / `costofpointegersreturned`，"pointegers" 语义不明，当前保留为复合词
- `shared_ads_sspa_ot_cost`：原字段 `sharedadssspaotcost`，"sspaot" 拆分不确定
- `shared_ads_sar_cost`：原字段 `sharedadssarcost`，"sar" 缩写含义不确定
- `refunds_rate`、`gross_rate`、`fba_returns_qty_rate`：`_rate` 字段含义模糊（百分点 vs 比率），当前保留原名，待确认后决定是否改为 `_pct` 或 `_rto`

## 维表判断明细

### ODS 疑似业务关联字段
| 字段 | 类型 | 说明 |
|------|------|------|
| `sids` | 字符串（复数） | 疑似店铺 sid，复数形式非标准维表单数 `sid` |
| `asins` | 字符串（复数） | 疑似 ASIN 码，复数形式非标准维表单数 `asin` |
| `store_name` | 字符串 | 疑似店铺名称，可类比 `acc_name` |
| `country` | 字符串 | 国家名称，可用于维表关联 |
| `country_code` | 字符串 | 国家代码，可用于维表关联 |
| `principal_real_name` | 字符串 | 店铺负责人姓名 |
| `brand_name` | 字符串 | 品牌名称 |
| `category_name` | 字符串 | 类目名称 |

### 标准维表触发信号检查

| 维表 | 信号 | 命中状态 | 说明 |
|------|------|----------|------|
| DIM-SHOP-001 | `shopid` / `saas_shop_id` | 未命中 | ODS 中无此字段 |
| DIM-SHOP-002 | `sid` / `lx_shop_id` | 接近但未命中 | `sids` 为复数形式，非精确 `sid`，脚本未自动识别 |
| DIM-SHOP-003 | `acc_name` + `platform` + `country` | 部分命中 | 有 `store_name`（接近 `acc_name`）和 `country`，但缺少 `platform` 字段 |
| DIM-SHOP-004 | `seller_id` + 国家码 | 未命中 | 无 `seller_id` / `sellerid` |
| DIM-MSKU-001 | `asin` + `shop_id` | 接近但未命中 | `asins` 为复数形式，且未解析出 `shop_id` |
| DIM-MSKU-002 | `asin` + 账号/站点 | 接近但未命中 | `asins` 为复数形式，非精确 `asin` |

### 未自动 JOIN 原因
1. `sids` / `asins` 均为复数形式字段名，与维表标准定义的 `sid` / `asin`（单数）不精确匹配，脚本未自动触发
2. DIM-SHOP-003 缺少必需的 `platform` 字段，无法组成三字段联合关联
3. 如需关联维表，建议人工确认 `sids` 是否为 `sid` 等价字段，再按 DIM-SHOP-002 标准 JOIN

### TODO_CONFIRM（维表相关）
- TODO_CONFIRM: 如 `sids` 等价于 `sid`，可补充 DIM-SHOP-002 JOIN（left join glcd.dim_shop_ich_dd on src.sids = dim_shop.lx_sid）
- TODO_CONFIRM: 如 `asins` 等价于 `asin` 且已取得 `shop_id`，可补充 DIM-MSKU-001 JOIN
- TODO_CONFIRM: `store_name` 是否可匹配 `dim_shop.acc_name`，配合 `country` 做 DIM-SHOP-003 联合关联（仍缺 platform）
