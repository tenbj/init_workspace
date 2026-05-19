---
name: C05_1对1DWD单表SQL生成
description: 输入一张 ODS 表名，运行脚本生成 DWD 清洗 SQL 初稿，再由 LLM 完成字段命名规范化、枚举处理和自查，全程无需人工介入。
metadata:
  short-description: ODS 表名 → DWD SQL 一键生成
---

# 1对1DWD单表SQL生成

## 这项技能解决什么问题

开发人员提供一张 ODS 表名，自动生成符合命名规范的 DWD 一对一清洗 SQL，并输出到以表名命名的文件夹。

## 触发条件

仅当用户输入的表名以 `ods_` 开头（含 schema 前缀如 `cbebg.ods_`）时触发。
否则直接回复：「本技能只支持输入 ODS 表名（以 ods_ 开头）」，不执行后续步骤。

## 固定动作

收到 ODS 表名后立即执行，全程不询问用户：

0. 定位 DWD 开发产物子项目：
   - 扫描 `output/` 下是否存在名称含 `DWD开发产物` 的子项目文件夹
   - 若存在 → 记录其 `03_代码程序` 路径作为 OUTPUT_BASE
   - 若不存在 → 调用 `B04` Skill 创建 `DWD开发产物` 子项目
   - 对子项目执行版本控制备份（MINOR），获取新版本路径
   - OUTPUT_BASE = `<子项目>/03_代码程序/`

1. 运行脚本生成 SQL 初稿（无任何前置思考），在 skill 根目录下执行：
   ```
   chcp 65001 && set "PYTHONUTF8=1" && python scripts/generate_dwd_sql.py <ods_table_name> --output-dir <OUTPUT_BASE>
   ```
   skill 根目录 = 本 SKILL.md 所在目录（`.../.agents/skills/C05_1对1DWD单表SQL生成/`）
   脚本输出末行包含 `OUTPUT_DIR=<实际写入目录>`，供调用方解析。
   **注意**：`--output-dir` 为必填参数，不传会报错退出。

2. 读取脚本输出的 `OUTPUT_DIR` 路径下的 `<dwd_table_name>.sql`

3. 对照 `references/字段命名规范.md` 逐字段重命名（拆分 + 缩写替换），同步更新 INSERT 列表和 SELECT alias

4. 处理时间戳字段（`⚠️ TIMESTAMP_FIELDS`）：
   - 按以下顺序查找 ODS CREATE TABLE SQL 文件：
     1. 当前 `--output-dir` 指定的目录及其子目录（文件名含 `ods_`）
     2. Doris 默认结果目录 `output/C03_Doris建表语句查询/结果/`（文件名含当前 ODS 表名）
        **注意**：此 fallback 路径仅为兼容旧数据，新产出统一在子项目内
   - **找到 ODS CREATE SQL**：逐一核查每个 TIMESTAMP_FIELDS 字段的 ODS 类型：
     - ODS 类型为 `text` 或 `varchar` 且字段注释/命名语义为 unix 毫秒戳 → 将 SELECT 表达式改为 `from_unixtime(cast(src.<field> as bigint) / 1000) as <field>`，同步更新 INSERT 字段列表
     - ODS 类型已为 `datetime` / `date` / `timestamp` → 保持 `src.<field>`，无需转换
   - **找不到 ODS CREATE SQL**：保留 `src.<field>` 原值，在该字段行末追加 `-- TODO_CONFIRM: 请核查 ODS 类型，如为 unix 毫秒戳需补充 from_unixtime 转换`
   - 在 SQL 头部 `LLM处理结果` 行记录每个 TIMESTAMP_FIELDS 字段的处理结论

5. 处理枚举字段和人工确认注释：
   - 保留脚本输出的 `⚠️ ENUM_FIELDS` 注释，不删除原始告警来源；在其下追加 `-- LLM处理结果：...`
   - 确认枚举语义的字段补 `<field>_desc` 占位列，SELECT 中写 `NULL as <field>_desc, -- TODO_CONFIRM: ...`
   - 不确认枚举语义的字段也保留顶部来源注释，并在 `LLM处理结果` 中说明未补原因
   - 再对最终 INSERT 字段名做二次扫描；凡字段名以 `_type`、`_status`、`_code`、`_flag`、`_level`、`_state`、`_mode`、`_kind`、`_category` 结尾且具备枚举语义的，必须补 `<field>_desc`
   - 所有 `NULL as *_desc` 都必须有行内 `TODO_CONFIRM` 注释，并写入同目录 `.md` 的「待处理」项，禁止静默忽略
   - 若脚本输出维表或其他人工确认告警（如 `⚠️  未检测到标准维表触发信号...`），保留原始注释并追加 `-- LLM处理结果：...`；凡 LLM 依据历史资料、经验规则或非脚本命中信号补充的维表 JOIN，必须在 JOIN 前写 `-- TODO_CONFIRM: ...`

6. 同目录 `.md` 必须固定包含「维表判断明细」模块：
   - 列出 ODS 中已扫描到的疑似业务关联字段
   - 说明命中的标准维表触发信号，或说明未命中的强信号字段
   - 说明接近但未自动 JOIN 的组合模式及原因
   - 所有需要人工确认的维表关系必须写成 `TODO_CONFIRM` 待处理项

7. 按 `references/自查清单.md` 逐项核对，全部通过才写文件

8. 将最终 SQL 覆盖写回文件；所有待人工确认点同步写入同目录 `.md`

9. 输出一行总结：DWD 表名、装载策略、维表、待处理项

## 什么时候读 references

- 字段命名拆分与缩写 → `references/字段命名规范.md`
- 自查核对项 → `references/自查清单.md`
- 装载策略与 SQL 骨架 → `references/装载策略判断.md`
- 维表 JOIN 片段 → `references/维表关联判断.md`
- DWD 表名推导 → `references/DWD命名规则.md`
- SQL 格式与枚举模板 → `references/SQL模板库.md`

## 边界

- 不询问、不确认、不暂停，执行到底
- 枚举字段只写 NULL 占位，不推断映射值；`NULL` 占位必须带 `TODO_CONFIRM` 行内注释
- 脚本非正常退出 → 错误写入 .md，告知用户
- 不修改审计字段（first_inserted_dt / etl_dt / last_updated_dt）
- 需要理解规则时读 references，不向用户提问
