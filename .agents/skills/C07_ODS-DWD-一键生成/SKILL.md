---
name: C07_ODS-DWD-一键生成
description: 输入 ODS 表名，定位 DWD 开发产物子项目，按 C03 → C05 → C06 顺序生成 DWD SQL 与字段 Excel，产物统一写入子项目目录。
metadata:
  short-description: ODS表名到DWD SQL及六列平台导入Excel，产物统一落在模型子项目
---

# ODS-DWD-一键生成

## 本地接入

先遵循当前工作区规则；按 B12 精确路由所需连接，按 B04/B08/B03 管理产物与进度。来源案例、账号、路径、人员和历史授权均不自动继承。

## 这项技能解决什么问题

用户只需提供一张 ODS 表名，本 skill 定位 DWD 开发产物子项目，按依赖顺序调用子 skill，将**所有产物**写入子项目的同一目录：

```
output/<DWD开发产物子项目>/03_代码程序/<dwd_name>/
  ├── cbebg.ods_xxx_<timestamp>.sql      ← Doris建表语句查询 产出
  ├── <dwd_name>.sql                     ← 1对1DWD单表SQL生成 产出
  ├── glcd.dim_xxx_<timestamp>.sql       ← Doris建表语句查询 产出（如有）
  └── 正式交付/02_字段文档/<dwd_name>_平台字段信息.xlsx ← C06平台六列导入件
```

子技能使用各自入口支持的路径参数，产物统一归入本模型子项目；以实际返回的路径继续交接。

## 先读哪些本地知识

- 按当前注册表解析 C03、C05、C18、C06，依次读取入口和所需引用。
- 读取 `references/交付衔接.md`，确认初稿、最终合同与平台导入件之间的边界。

## 触发条件

用户输入 ODS 表名（以 `ods_` 开头，含或不含 schema 前缀）且需要同时生成 DWD SQL 和字段 Excel 时触发。

## 固定动作

收到 ODS 表名后，全程不询问用户，**严格按以下顺序执行**：

1. **定位 DWD 开发产物子项目，推导 DWD 表名，确定统一输出目录**
   - 扫描 `output/` 下是否存在名称含 `DWD开发产物` 的子项目文件夹
   - 若不存在 → 调用 `B04` Skill 创建 `DWD开发产物` 子项目
   - 保持子项目路径稳定，独立更新 `版本记录.md`；不自动备份
   - 按注册表解析 C05，读取其 `references/DWD命名规则.md`，从 ODS 表名推导 DWD 表名
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
   先按 C18 补齐最终DWD建表SQL和已确认字段合同，不能把C05初稿或ODS主键当最终设计。把最终DDL、加工SQL、字段合同及OUTPUT_DIR交给 C06；从统一平台模板生成`{dwd_name}_平台字段信息.xlsx`，不再使用旧11列设计表生成入口。源DDL仅供设计溯源，不作为Excel类型和主键的直接依据。

5. **自查**
   - [ ] OUTPUT_DIR 下存在 `<dwd_name>.sql` 或 C18 正式交付的加工 SQL
   - [ ] C03 返回的 ODS 建表文件实际存在，后续使用该确切路径
   - [ ] 正式交付包含六列`<dwd_name>_平台字段信息.xlsx`，与最终DDL/INSERT/字段合同的校验通过，不能只检查文件存在
   - [ ] 配套开发说明中时间戳及枚举告警均有处理结论，无未处理项

6. **输出最终总结**
   ```
   ✅ 生成完成
   输出目录  : <DWD开发产物子项目>/03_代码程序/<dwd_name>/
   DWD SQL   : <dwd_name>.sql
   ODS SQL   : <ods_name>_<timestamp>.sql
   平台导入 Excel: <dwd_name>_平台字段信息.xlsx
   待处理项  : <TODO_CONFIRM 汇总列表>
   ```

## 什么时候再读本 skill 的 references

- 确认各步骤的文件路径、最终化要求与失败处理时读 `references/交付衔接.md`。

## 边界

- 步骤 2（`C03`）必须在步骤 3（`C05`）之前
- 依子技能实际参数指定输出位置；C06 使用 `--output` 与 `--work-dir`，不把不存在的 `--output-dir` 参数传入 C06
- 若任何子 skill 失败，停止后续步骤，将错误原文返回用户
