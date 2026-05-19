---
name: C04_临时数据存储
description: 写入沙盒技能。连接测试库 test，为分析中间态数据执行 DDL（建表）和 DML（插入）。严禁用于生产环境或查询任务。
metadata:
  short-description: 向测试库写入中间态数据的沙盒底座
---

# 临时数据存储

## 这项技能解决什么问题

在复杂分析任务中，LLM 需要一片隔离区域存放预聚合中间产物或验证数据，同时不能污染生产环境。
本技能将写操作限定在环境变量配置的测试集群 `test` 库内，提供安全的临时落盘能力。

## 先读哪些本地知识

- 需要加载客户端时，读 `references/加载方式.md`
- 需要了解建表或写入接口时，读 `references/接口说明.md`

## 固定动作

1. 按 `references/加载方式.md` 加载 `scripts/doris_storage_client.py`
2. 用 `execute()` 执行 DDL（建表）或单条 DML（插入）
3. 批量写入时用 `execute_many()`

## 什么时候再读 references

- 忘记加载方式 → `references/加载方式.md`
- 不确定 `execute` 和 `execute_many` 的参数格式 → `references/接口说明.md`

## 边界

- 只连接环境变量配置的测试集群，默认库为 `test`，物理隔离生产环境
- 不用于查询任务，读数据请用 `数仓生产库查询` 或 `ClickHouse查询` 技能
- 连接信息必须从环境变量读取，不得写入仓库或临时文件
- 建表时必须加 `IF NOT EXISTS`，防止重复执行报错
