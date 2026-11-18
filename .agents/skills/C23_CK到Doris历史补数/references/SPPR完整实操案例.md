# SPPR 完整实操案例

2026-10-22 实际执行，用户已确认本组结果无问题。下面是已完成的历史证据；重新执行时必须重新探查，不能复用旧范围和实例号。

## 1. 对象、实际源与模型

- Excel 第18行：CK `ck_ods_db.ods_advertised_sppr_cluster` → Doris `cbebg.ods_tenant00001_t_oms_advertised_sppr`。
- 从目标模型关联 ETL 确认，Doris 线上日常工作流 180881996790050 第3版读取 `Tenant00001.dbo.t_OmsAdvertisedSPPR`；按 Date 取近期，默认前两个月首日至当天。
- CK 仓库读取同名源表，部分 NULL 默认化；旧任务每次运行的物理连接参数未完整回溯，因此仅写逻辑源表一致及数据覆盖证据。
- Doris 为 DUPLICATE KEY(Id,ShopId,SiteId,Date)，不按该排序键合并。历史 Id 经本次实际核验唯一，不据此宣称已确定最小业务键。

## 2. 三方探查和确认

| 日期范围 | Doris 实际源 | CK | 补前 Doris | 实际缺口 |
|---|---:|---:|---:|---:|
| 2022-11-01～2025-09-30 | 0 | 3,284,836 | 0 | 3,284,836 |
| 2025-10-01～2026-10-21 | 1,612,693 | 1,612,693 | 1,612,693 | 0 |
| 合计 | 1,612,693 | 4,897,529 | 1,612,693 | 3,284,836 |

源 Date NULL=0，当前源 Id 唯一。近期386天逐日相等，并按13个月完成全部1,612,693条 Id/Date 出现频次的三方比较，无缺失/多出。旧历史源当前不存在已证实，物理删除机制未查日志。历史候选与 Doris 缺口在本组恰好相同，不推广到其他表。

在聊天打印三方表、补数范围和单批数量，用户确认本组；随后用户要求所有分区语句先展示、查权限，无权限由用户执行、有权限也要确认后执行。

## 3. 分区脚本和回读

原分区 p2025—p2027；缺2022—2024。原动态属性 enable=true、time_unit=YEAR、time_zone=Asia/Shanghai、start=-2147483648、end=1、create_history_partition=false、history_partition_num=-1、prefix=p。

当前直连读账号只有 SELECT，无 ALTER；查看 writer 账号授权也被拒绝，未假定其拥有 DDL 权限。交付 [原样分区脚本](../assets/sppr_case/prepare_history_partitions.sql)：暂关动态→ADD IF NOT EXISTS p2022/p2023/p2024→恢复 true→SHOW PARTITIONS/CREATE TABLE。**DDL 由用户执行，代理没有执行生产 ALTER。**

用户通知完成后代理回读：p2022—p2027 都在，三个新增分区年度边界正确、NORMAL，各4桶3副本；动态开关 true，其余原属性保留。之后才进行补数。

## 4. 六参数与单段设计

实际读取/写入3,284,836，小于约500万，设计一段 StartTime=2022-11-01、EndTime=2025-09-30；提交前 DELETE 命中0条。两端日期都包含。

58列=55个业务字段+3个审计时间。Date、DateUTC、LocalCreatedTime 与审计时间字符串化适配 reader；实际历史投影3条、58列通过。完整文件在 assets/sppr_case/：

| 文件 | 用途 |
|---|---|
| query.sql / preSql.sql | 普通可读 SQL，保留参数占位 |
| parameters.json | 当时保存的六参数，JSON 解码后才是实际参数字符串 |
| sql.txt / columns.txt / table.txt / StartTime.txt / EndTime.txt / preSql.txt | 各参数整块录入值，沿用已成功模板转义 |
| prepare_history_partitions.sql | 用户执行的完整分区脚本，含恢复开关与回读 |

该组 DELETE 为：

```sql
DELETE FROM cbebg.ods_tenant00001_t_oms_advertised_sppr
WHERE Date >= '${StartTime}'
  AND Date <= '${EndTime} 23:59:59.999'
  AND Date >= '2022-11-01'
  AND Date < '2025-10-01';
```

SELECT 具有同样的参数和固定日期保护。固定界限保护近期，并不意味着今后每张表都使用这个日期。

## 5. 工作流保存、录入和运行

从财务 His-Init 工作流187598929900705第6版复制，原模板未改。目标项目136216090360000；新工作流187605058261153第2版，名称 `[His-Init]ods_tenant00001_t_oms_advertised_sppr`，描述为目标表名；单一 DataX 节点187605058261152第2版“历史初始化”。

六参数逐项整块粘贴，通过临时剪贴板标识和复制全文比对排除旧内容；保存后六值再次完全一致，其他模板配置不变。sql/preSql 引号采用一层字面反斜杠 u0027，匹配成功模板。定义 ONLINE、SERIAL_WAIT，定时不存在/未启用。

启动显式传两个日期，通知策略“都不发”（NONE），不选原生补数、空跑或测试。仅提交一次，实例623451的 commandParam 回读包含2022-11-01/2025-09-30。2026-10-22 11:09:47至11:11:00，73秒 SUCCESS，无失败重试。成功后未打开节点日志，单独查询数据验收。

## 6. 验收与回写

| 范围 | CK | 补后 Doris | 核验证据 |
|---|---:|---:|---|
| 历史 | 3,284,836 | 3,284,836 | 35个月全部 Id/Date 及频次比较，缺失0、多出0 |
| 近期 | 1,612,693 | 1,612,693 | 补后386天逐日与补前一致；完整键三方比较为补前证据 |
| 全表 | 4,897,529 | 4,897,529 | 全表逐日数量一致 |

历史每年最小/最大 Id 各20条，共160条×55个业务字段，按目标 Decimal 精度和时间标准化比较，差异0；3个装载审计时间排除。没有进行全表55业务字段逐值比较，不把抽样结论扩大。

Excel 第18行 R、Z:AF 八格已回写：CK/Doris 各4,897,529，已补齐验收通过，分类“历史数据差异（已补齐）”。其他 XML 单元格、样式及压缩包条目逐项保持一致并渲染检查。His-Init 保持 ONLINE/串行等待，定时未开。用户随后确认本组无问题，授权沉淀本 Skill。

## 7. 证据追溯

本案例原始任务证据为 row18_execution_20261022 中的 preflight、source_preflight、current_id_comparison、parameter_preflight、partition_privileges、partitions_after_user_change、saved_workflow、clipboard_verification、run_result、postload_acceptance、historical_field_sample 等 JSON；均以实际查询时点为准。Skill 只携带脱敏 SQL/参数和此摘要，不依赖旧任务目录才能执行，也不复制原始账号、会话或日志。
