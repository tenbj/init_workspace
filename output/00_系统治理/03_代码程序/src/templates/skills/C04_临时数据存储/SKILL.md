---
name: C04_临时数据存储
description: 写入沙盒技能。连接测试库 test，为分析中间态数据执行 DDL（建表）和 DML（插入）。严禁用于生产环境或查询任务。
metadata:
  short-description: 向测试库写入中间态数据的沙盒底座
---

# 临时数据存储

## 本地接入

先遵循当前工作区规则；按 B12 精确路由所需连接，按 B04/B08/B03 管理产物与进度。来源案例、账号、路径、人员和历史授权均不自动继承。

## 这项技能解决什么问题

在复杂分析任务中，LLM 需要一片隔离区域存放预聚合中间产物或验证数据，同时不能污染生产环境。
本技能使用 `.envs` 中 `doris.test.writer` 的测试写入身份，默认连接库必须为 `test`。具体访问范围仍由账号权限与本次授权共同限定。

## 先读哪些本地知识

- 需要加载客户端时，读 `references/加载方式.md`
- 需要了解建表或写入接口时，读 `references/接口说明.md`

## 固定动作

1. 按 `references/加载方式.md` 加载 `scripts/doris_storage_client.py`
2. 用 `execute()` 执行 DDL（建表）或单条 DML（插入）
3. 批量写入时用 `execute_many()`

## 什么时候再读本 skill 的 references

- 忘记加载方式 → `references/加载方式.md`
- 不确定 `execute` 和 `execute_many` 的参数格式 → `references/接口说明.md`

## 边界

- 固定加载 `.envs` 的 `doris.test.writer`，默认库必须为 `test`；不能凭连接名称宣称物理隔离生产环境
- 不用于查询任务，读数据请用 `数仓生产库查询` 或 按 B12 路由的 ClickHouse 只读连接
- 连接通过 `.envs/env_manager.py` 加载测试写入环境，不得把凭据写入仓库或临时文件
- 建表时必须加 `IF NOT EXISTS`，防止重复执行报错
