---
name: C02_数仓生产库查询
description: 只读连接生产 Doris 数仓，执行 SQL 查询并返回结构化结果；仅适用于 Doris，不用于平台 MySQL 或其他来源数据库。
metadata:
  short-description: 只读查询生产 Doris 数仓的基础底座
---

# 数仓生产库查询

## 本地接入

先遵循当前工作区规则；按 B12 精确路由所需连接，按 B04/B08/B03 管理产物与进度。来源案例、账号、路径、人员和历史授权均不自动继承。

先读 `references/本地接入.md`。

## 这项技能解决什么问题

为 LLM 提供直接查询生产 Doris 数仓的能力，支持多库探查、Schema 反查、SQL 执行与结果格式化。
本技能是只读底座，不具备写入能力，供上层技能调用。

本工作区的“数仓”专指 Doris；平台 MySQL 不属于数仓，不使用本技能。连接固定为 `.envs` 中的 `doris.prod.readonly`，具体加载见下方分册。

## 先读哪些本地知识

- 需要加载客户端时，读 `references/加载方式.md`
- 需要了解可用接口时，读 `references/接口说明.md`
- 需要跨库查询或不知道有哪些库时，读 `references/多库说明.md`

## 固定动作

1. 按 `references/加载方式.md` 加载 `scripts/doris_query_client.py`
2. 根据任务选择接口：探查用 `get_databases / get_tables / describe_table`，执行用 `query()`
3. 检查返回的 `error` 字段，无误后 `print(client.format_result(result))`

## 什么时候再读本 skill 的 references

- 忘记加载方式 → `references/加载方式.md`
- 不知道某个方法的参数或返回结构 → `references/接口说明.md`
- 需要跨库 JOIN 或列出所有库 → `references/多库说明.md`

## 边界

- 只允许只读操作，写操作由客户端内置守卫拦截，无需额外判断
- 连接通过 `.envs/env_manager.py` 加载登记的生产只读环境，不得把凭据写入仓库或临时文件
- 不负责生成 SQL，SQL 由调用方（上层 skill 或 LLM）提供
- 不做数据持久化，写入需使用 C04
- 结果必须通过 `print()` 输出到 stdout，这是返回给 LLM 的唯一出口
