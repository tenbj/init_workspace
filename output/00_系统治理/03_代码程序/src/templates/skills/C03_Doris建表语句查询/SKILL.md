---
name: C03_Doris建表语句查询
description: 运行脚本查询 Doris 表的 CREATE TABLE 语句并保存为本地 SQL 文件。禁止 LLM 直接构造或执行任何数据库查询，只能调用脚本。
metadata:
  short-description: 运行脚本获取 SHOW CREATE TABLE，禁止 LLM 自行查询数据库
---

# Doris建表语句查询

## 这项技能解决什么问题

为上层 skill 提供标准化的 Doris 建表语句获取能力。输入库名.表名，运行脚本执行 `SHOW CREATE TABLE`，将结果保存为带时间戳的本地 SQL 文件，返回文件路径供调用方使用。

## 固定动作

收到表名后立即执行，不询问用户：

1. 在 skill 根目录下运行脚本：
   ```
   chcp 65001 && set "PYTHONUTF8=1" && python scripts/get_create_table.py <库名.表名> --output-dir <目录>
   ```
   - `--output-dir` 为必填参数，不指定时脚本报错退出
   - 调用方应传入 DWD 开发产物子项目的 `03_代码程序/<dwd_name>/` 路径
   - 目录不存在时脚本自动创建
   - skill 根目录 = 本 SKILL.md 所在目录（`.agents/skills/C03_Doris建表语句查询/`）

2. 从脚本输出末行读取保存路径（格式：`[OK] 建表语句已保存：<path>`）

3. 将 SQL 文件绝对路径返回给调用方

## 什么时候读 references

- 脚本报错或连接失败 → `references/异常处理.md`

## 边界

- **禁止**：LLM 自行 import doris_query_client、构造 pymysql 连接、或直接执行任何 SQL
- **只允许**：运行 `scripts/get_create_table.py`
- 每次调用只查一张表；多张表需多次独立调用
- 脚本异常退出时，将错误原文返回调用方，不自行重试、不推断结果
