---
name: C06_DWD字段信息Excel生成
description: 给定 DWD 表名，复用同目录已有建表语句（或按需拉取），运行脚本生成字段信息 Excel 文件，所有产物统一落到 DWD 输出目录。
metadata:
  short-description: DWD 表名 → 字段信息 xlsx，产物与 DWD SQL 同目录
---

# DWD字段信息Excel生成

## 这项技能解决什么问题

给定一张 DWD 表名，定位其 INSERT SQL 文件，自动拉取所依赖的 ODS 和 DIM 建表语句（优先复用已有文件），运行脚本生成标准字段信息 xlsx 文件。所有产物（ODS SQL、DIM SQL、xlsx）统一保存到 DWD 输出目录。

## 触发条件

用户提供 DWD 表名（以 `dwd_` 开头）且需要生成字段信息 Excel 时触发。

## 固定动作

收到 DWD 表名后，全程不询问用户：

**输出目录**（以下简称 OUTPUT_DIR）：
- 单独运行时：先定位 DWD 开发产物子项目，使用其 `03_代码程序/<dwd_table_name>/`
- 由编排器调用时：编排器传入的统一目录

**DWD SQL 来源目录**（DWD SQL 始终由 `1对1DWD单表SQL生成` 生成，在子项目内）：
扫描 DWD 开发产物子项目的 `03_代码程序/` 下 `<dwd_table_name>/<dwd_table_name>.sql`

1. **定位 DWD SQL 文件**
   扫描 DWD 开发产物子项目的 `03_代码程序/` 下 `<dwd_table_name>/<dwd_table_name>.sql`
   读取文件，提取：
   - INSERT 字段列表
   - FROM 子句中的 ODS 表名（格式：`schema.table alias`）
   - LEFT JOIN 子句中的所有 DIM 实体表名和别名（跳过子查询，取实体表名）

2. **获取 ODS 建表语句**
   先在 `OUTPUT_DIR` 查找已有 ODS CREATE SQL 文件（文件名含 `ods_`）。
   - 已存在 → 直接使用，跳过查询
   - 不存在 → 调用 `Doris建表语句查询` skill，加 `--output-dir <OUTPUT_DIR>`，将 SQL 文件保存到 OUTPUT_DIR

3. **获取 DIM 建表语句**（如有 DIM 关联）
   对每张 DIM 实体表，先在 `OUTPUT_DIR` 查找（文件名含表名）。
   - 已存在 → 直接使用
   - 不存在 → 调用 `Doris建表语句查询` skill，加 `--output-dir <OUTPUT_DIR>`

4. **运行 Excel 生成脚本**
   在 skill 根目录下执行：
   ```
   chcp 65001 && set "PYTHONUTF8=1" && python scripts/generate_field_excel.py \
     --dwd-sql   <DWD子项目>/03_代码程序/<dwd_name>/<dwd_name>.sql \
     --ods-sql   <OUTPUT_DIR>/<ods_sql_file> \
     --dim-sql   <OUTPUT_DIR>/<dim1_sql_file> \
     --dim-sql   <OUTPUT_DIR>/<dim2_sql_file> \
     --output    <OUTPUT_DIR>/<dwd_name>_字段信息.xlsx
   ```
   skill 根目录 = 本 SKILL.md 所在目录（`.agents/skills/C06_DWD字段信息Excel生成/`）

5. **自查**（对照 `references/自查清单.md`）：全部通过才结束

6. **输出一行总结**
   报告 xlsx 文件路径、字段总数、系统字段数、业务字段数，以及 ODS/DIM SQL 是复用还是新查。

## 什么时候读 references

- 字段类型映射规则（text/int/datetime → 日期/数值/文本）→ `references/字段类型映射规则.md`
- 自查项目 → `references/自查清单.md`
- 脚本报错 → 检查各 SQL 文件路径是否存在

## 边界

- DWD SQL 文件必须已存在（由 `1对1DWD单表SQL生成` 提前生成），本 skill 不生成 SQL
- 只处理 `INSERT OVERWRITE ... SELECT` 格式的 DWD SQL
- 所有产物（ODS SQL、DIM SQL、xlsx）统一保存到 `<DWD输出目录>`，不写其他路径
- 脚本异常退出时报告错误，不自行推断字段信息
- 已存在同名 xlsx 时覆盖
