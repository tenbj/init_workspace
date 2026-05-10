# DWD 表命名规则

## 命名格式

```
cbebg.dwd_{域}_{业务名}_{ilu/flu}_dd
```

## 推导步骤

1. 取 ODS 表名去掉 schema 前缀（如 `cbebg.`）
2. 去掉常见 ODS 前缀：`ods_realtime_db_t_`、`ods_realtime_`、`ods_sync_`、`ods_api_`、`ods_`
3. 剩余部分即为业务名，从中推断域前缀
4. 根据装载策略拼接 `_ilu_dd` 或 `_flu_dd`

## 域前缀对照

| 业务名前缀 | 域 | 说明 |
|----------|-----|-----|
| `ads_` | ads | 广告 |
| `trd_` | trd | 交易 |
| `inv_` | inv | 库存 |
| `fl_` | fl | 物流 |
| `fin_` | fin | 财务 |
| `mkt_` | mkt | 营销 |
| `op_` | op | 运营 |
| `cs_` | cs | 客服 |
| `cst_` | cst | 客户 |
| `lx_` | 看二级前缀 | 领星系统，继续看后续词 |

## 示例

| ODS 表名 | DWD 表名（增量） | DWD 表名（全量） |
|---------|----------------|----------------|
| `ods_realtime_db_t_lx_newad_hasadgroups` | `dwd_ads_lx_new_ad_has_ad_groups_ilu_dd` | `dwd_ads_lx_new_ad_has_ad_groups_flu_dd` |
| `ods_realtime_db_t_lx_newad_hsa_campaigns` | `dwd_ads_lx_new_ad_hsa_campaigns_ilu_dd` | `dwd_ads_lx_new_ad_hsa_campaigns_flu_dd` |
| `ods_realtime_db_t_amz_report_xxx` | `dwd_ads_amz_xxx_ilu_dd` | `dwd_ads_amz_xxx_flu_dd` |

## 注意

- 频率固定为每日（`dd`）
- 域从业务名前缀自动推断，无法推断时报 ⚠️ 提示人工确认
