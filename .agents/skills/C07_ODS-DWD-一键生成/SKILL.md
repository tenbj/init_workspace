---
name: C07_ODS-DWD-一键生成
description: 输入 ODS 表名，定位 DWD 开发产物子项目，按 C03 → C05 → C06 顺序生成 DWD SQL 与字段 Excel，产物统一写入子项目目录。
metadata:
  short-description: ODS 表名 → DWD SQL + 字段信息 xlsx，产物统一落在本 skill 输出目录
---

# ODS-DWD-一键生成

## 这项技能解决什么问题

用户只需提供一张 ODS 表名，本 skill 定位 DWD 开发产物子项目，按依赖顺序调用子 skill，将**所有产物**写入子项目的同一目录：

```
output/<DWD开发产物子项目>/03_代码程序/<dwd_name>/
  ├── cbebg.ods_xxx_<timestamp>.sql      ← Doris建表语句查询 产出
  ├── <dwd_name>.sql                     ← 1对1DWD单表SQL生成 产出
  ├── glcd.dim_xxx_<timestamp>.sql       ← Doris建表语句查询 产出（如有）
  └── <dwd_name>_字段信息.xlsx           ← DWD字段信息Excel生成 产出
```

所有子 skill 均通过 `--output-dir` 写入统一目录，产物归入标准子项目管理体系。

## 触发条件

用户输入 ODS 表名（以 `ods_` 开头，含或不含 schema 前缀）且需要同时生成 DWD SQL 和字段 Excel 时触发。

## 固定动作

收到 ODS 表名后，全程不询问用户，**严格按以下顺序执行**：

1. **定位 DWD 开发产物子项目，推导 DWD 表名，确定统一输出目录**
   - 扫描 `output/` 下是否存在名称含 `DWD开发产物` 的子项目文件夹
   - 若不存在 → 调用 `B04` Skill 创建 `DWD开发产物` 子项目
   - 对子项目执行版本控制备份（MINOR），获取新版本路径
   - 读取 `1对1DWD单表SQL生成/references/DWD命名规则.md`，从 ODS 表名推导 DWD 表名
   ```
   OUTPUT_DIR = <DWD开发产物子项目>/03_代码程序/<dwd_name>/
   ```
   目录不存在时创建。**后续所有步骤均使用此目录。**

2. **调用 `C03` 查询 ODS 建表语句**
   ```
   python scripts/get_create_table.py <ods_table> --output-dir <OUTPUT_DIR>
   ```
   ODS CREATE SQL 直接写入 OUTPUT_DIR。

3. **调用 `C05` 生成 DWD SQL**
   ```
   python scripts/generate_dwd_sql.py <ods_table> --output-dir <OUTPUT_DIR>
   ```
   DWD SQL 写入 `<OUTPUT_DIR>/<dwd_name>/`（脚本在 OUTPUT_DIR 下按表名建子目录）。
   LLM 时间戳处理阶段在 OUTPUT_DIR 中查找 ODS CREATE SQL（步骤 2 已写入，必然存在）。

4. **调用 `C06` 生成字段信息 Excel**
   传入 DWD 表名，并告知 OUTPUT_DIR。该 skill 将 ODS/DIM SQL 查询和 xlsx 均写入 OUTPUT_DIR。

5. **自查**
   - [ ] OUTPUT_DIR 下存在 `<dwd_name>/<dwd_name>.sql`
   - [ ] OUTPUT_DIR 下存在至少一个 `ods_*.sql` 文件
   - [ ] OUTPUT_DIR 下存在 `<dwd_name>_字段信息.xlsx`
   - [ ] DWD SQL 中 `⚠️ TIMESTAMP_FIELDS` 已全部有 `LLM处理结果` 行，无未处理项

6. **输出最终总结**
   ```
   ✅ 生成完成
   输出目录  : <DWD开发产物子项目>/03_代码程序/<dwd_name>/
   DWD SQL   : <dwd_name>.sql
   ODS SQL   : <ods_name>_<timestamp>.sql
   字段 Excel: <dwd_name>_字段信息.xlsx
   待处理项  : <TODO_CONFIRM 汇总列表>
   ```

## 边界

- 步骤 2（`C03`）必须在步骤 3（`C05`）之前
- 所有子 skill 均通过 `--output-dir` 写入统一目录，不做任何文件移动
- 若任何子 skill 失败，停止后续步骤，将错误原文返回用户
