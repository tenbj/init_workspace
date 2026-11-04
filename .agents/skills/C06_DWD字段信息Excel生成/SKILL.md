---
name: C06_DWD字段信息Excel生成
description: 从最终DWD建表SQL、加工SQL和已确认字段合同生成平台六列Excel，开发阶段即可直接导入，不再根据ODS字段猜类型。
---

# C06_DWD字段信息Excel生成

## 本地接入

先遵循当前工作区规则；按 B12 精确路由所需连接，按 B04/B08/B03 管理产物与进度。来源案例、账号、路径、人员和历史授权均不自动继承。

## 这项技能解决什么问题

消费 C18 的最终DDL、加工SQL、字段合同JSON。字段合同包含有序fields数组，每项明确name、type、label、comment、nullable、physical_primary_key；不能根据源表主键、字段后缀或英文名猜目标定义。

默认输出平台导入件`正式交付/02_字段文档/{规范表名}_平台字段信息.xlsx`，只有一个工作表和六列：排序序号、Type、字段原名、字段名、字段释义、主键。设计说明Excel可以另存，但必须标注“阅读用，不能导入”。

## 先读哪些本地知识

- 按当前注册表解析 C18，读取其 `references/平台建模交接.md`，以最终字段合同、DDL和加工SQL为依据。
- 读取本技能 `references/自查清单.md` 与 `references/字段类型映射规则.md`，旧源表推断口径不能覆盖最终合同。

## 固定动作

1. 定位本模型子项目及最终DDL/SQL/字段合同；已有确认直接复用。缺最终合同则回 C18 完成，不能继续输出猜测值。
2. 读取 C18 的`references/平台建模交接.md`。使用其`assets/平台字段信息模板.xlsx`和共用生成器；不要新建一套Workbook布局。平台导出只用于比对模板是否变化，不在建模阶段重填Excel。
3. 按电子表格技能加载官方运行时，在本模型开发目录的工作子目录建立指向官方包的node_modules链接。执行该技能要求的artifact operation marker。
4. 运行唯一入口（路径均传绝对路径，node来自load_workspace_dependencies）：

```text
python scripts/generate_field_excel.py --contract <字段合同.json> --ddl <最终建表.sql> --dwd-sql <最终加工.sql> --output <表名_平台字段信息.xlsx> --work-dir <开发材料/字段Excel生成> --node <官方node可执行文件>
```

5. 脚本先核对合同、最终DDL和INSERT，调用 C18 共用生成器，再从落盘Excel回读核验；核验失败不能交付。保留模板hash、文件hash及校验回执到开发材料。核对生成预览，移除临时依赖链接。
6. C18交付总检查必须同时通过；回复直接可选的导入文件，说明“静态一致性已通过”与“平台导入已验证”的区别。此步骤不需要连接数据库。

## 什么时候再读本 skill 的 references

- 确认交付检查项时读 `references/自查清单.md`；核对类型时读 `references/字段类型映射规则.md`。
- 平台模板、审计字段或主键约定有疑问时回到 C18 的 `references/平台建模交接.md`。

## 边界与旧入口迁移

- 原脚本从ODS/DIM推断字段并输出11列设计表，已停用；旧参数`--ods-sql/--dim-sql`不能生成正式平台交付。
- `--dwd-sql`接受显式字段清单的INSERT INTO或INSERT OVERWRITE，要求恰好一个目标INSERT；未覆盖的SQL形式明确报错，不能回退猜测。
- 六列结构、审计顺序、物理主键、中文名和COMMENT规则在 C18 维护；不在本技能复制第二套生成代码。
- 全部产物归本模型output子项目；不改源模板，不自动备份，不执行平台或数据库写入。
