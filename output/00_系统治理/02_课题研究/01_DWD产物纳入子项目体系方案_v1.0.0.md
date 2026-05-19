# DWD 系列 Skill 产物纳入子项目管理体系 — 方案 A 详细实施计划

> 本文档记录 DWD 系列 Skill 的输出路径如何从"硬编码绕过子项目管理"改为"完全融入子项目体系"的全部设计决策和具体修改点。

---

## 一、问题背景

### 1.1 现象

`output/` 下出现不符合 `{编号}_{主题}_v{x.y.z}` 命名规范的文件夹 `1对1DWD单表SQL生成/`。

### 1.2 根因

4 个 DWD 系列 Skill 的脚本/SKILL.md 中硬编码了默认输出路径，单独运行时直接在 `output/` 下创建以 Skill 名命名的文件夹，绕过了子项目管理 Skill 的标准流程。

| Skill | 脚本硬编码默认路径 | SKILL.md 描述 |
|-------|-------------------|---------------|
| `1对1DWD单表SQL生成` | `generate_dwd_sql.py` L30：`output/1对1DWD单表SQL生成/` | L25：默认输出到该路径 |
| `Doris建表语句查询` | `get_create_table.py` L30：`output/Doris建表语句查询/结果/` | L23：默认目录 |
| `DWD字段信息Excel生成` | 脚本无硬编码（纯 SKILL.md 描述） | L23：`output/DWD字段信息Excel生成/<dwd>/` |
| `ODS-DWD-一键生成` | 无脚本（编排器角色） | L15：`output/ODS-DWD-一键生成/<dwd>/` |

### 1.3 方案选择

**方案 A：Skill 产物完全纳入标准子项目** ✅ 用户已确认

---

## 二、目标架构

### 2.1 子项目设计

创建一个标准子项目 `01_DWD开发产物_v1.0.0`，所有 DWD 系列 Skill 的产物统一存放在其 `03_代码程序_v*` 子文件夹下。

```
output/01_DWD开发产物_v1.0.0/
├── 目录.md
├── 版本记录.md
├── 01_问题答疑/
├── 02_课题研究/
└── 03_代码程序/               ← DWD 产物统一落这里
    └── dwd_fin_lx_finance_report_msku_list_flu_dd/
        ├── dwd_fin_lx_finance_report_msku_list_flu_dd.sql
        ├── dwd_fin_lx_finance_report_msku_list_flu_dd.md
        ├── cbebg.ods_xxx_20260507.sql         ← Doris 建表查询产出
        └── dwd_xxx_字段信息.xlsx               ← Excel 生成产出
```

> `03_代码程序_v*` 内部文件保留工具链原生命名，不强制 `{NN}_{标题}_v{x.y.z}` 文件级版本。每个 DWD 表的产物放在以 DWD 表名命名的子目录下。

### 2.2 路径常量变化

| 场景 | 旧路径 | 新路径 |
|------|--------|--------|
| DWD SQL 单独生成 | `output/1对1DWD单表SQL生成/<dwd>/` | `output/01_DWD开发产物_vX.Y.Z/03_代码程序_vA.B.C/<dwd>/` |
| Doris 建表查询默认 | `output/Doris建表语句查询/结果/` | 同 DWD 表子目录（由 `--output-dir` 指定） |
| DWD Excel 单独生成 | `output/DWD字段信息Excel生成/<dwd>/` | 同 DWD 表子目录（由编排器指定） |
| ODS-DWD 一键生成 | `output/ODS-DWD-一键生成/<dwd>/` | 同 DWD 表子目录（编排器统一指定） |

---

## 三、具体修改点

### 3.1 创建标准子项目

**操作**：调用子项目管理 Skill

```powershell
powershell -ExecutionPolicy Bypass -File ".agents\skills\子项目管理\scripts\new_project.ps1" -Topic "DWD开发产物"
```

**产出**：`output/01_DWD开发产物_v1.0.0/`（含标准三分类子文件夹 + 目录.md + 版本记录.md）

**后续**：初始化 `.memory/对话记录/01_DWD开发产物_v1.0.0.md`，更新全局知识地图

---

### 3.2 迁移现有产物

**操作**：

1. 将 `output/1对1DWD单表SQL生成/dwd_fin_lx_finance_report_msku_list_flu_dd/` 整个移入 `output/01_DWD开发产物_v1.0.0/03_代码程序/`
2. 删除空的 `output/1对1DWD单表SQL生成/`
3. 将 `03_代码程序` 重命名为 `03_代码程序`（首次有内容）

**后续**：删除不合规的对话记录 `.memory/对话记录/1对1DWD单表SQL生成.md`，将有效历史内容迁入新的 `01_DWD开发产物_v1.0.0.md`

---

### 3.3 修改 `1对1DWD单表SQL生成` Skill

#### 3.3.1 修改 `scripts/generate_dwd_sql.py`

| 行号 | 当前代码 | 修改为 |
|------|---------|--------|
| L30 | `OUTPUT_DIR = PROJECT_ROOT / "output" / "1对1DWD单表SQL生成"` | `OUTPUT_DIR = None  # 必须通过 --output-dir 指定` |
| L416 | `output_dir = Path(args.output_dir) if args.output_dir else OUTPUT_DIR` | 增加检查：若 `args.output_dir` 为空则报错退出 |

**修改后行为**：不传 `--output-dir` 时脚本报错 `❌ 必须通过 --output-dir 指定输出目录`，而不是默认写到 `output/1对1DWD单表SQL生成/`。

> ⚠️ 此文件是 `.py`，不受 BOM 约束，可直接用编辑工具修改。

#### 3.3.2 修改 `SKILL.md`

| 位置 | 当前描述 | 修改为 |
|------|---------|--------|
| L25 注释 | `默认输出到 output/1对1DWD单表SQL生成/` | 删除这行注释 |
| L26 单独运行 | `chcp 65001 && set ... && python scripts/generate_dwd_sql.py <ods>` | 新增前置步骤：定位或创建 `DWD开发产物` 子项目 |
| L40-41 时间戳查找路径 | `output/1对1DWD单表SQL生成/<dwd>/` | 改为 `当前 --output-dir 指定的目录` |

**新增前置步骤（SKILL.md 固定动作第 0 步）**：

```markdown
0. 定位 DWD 开发产物子项目：
   - 扫描 output/ 下是否存在名称含 "DWD开发产物" 的子项目
   - 若存在 → 记录其 `03_代码程序_v*` 路径作为 OUTPUT_BASE
   - 若不存在 → 调用子项目管理 Skill 创建 `DWD开发产物` 子项目
   - OUTPUT_DIR = OUTPUT_BASE（脚本会在其下自建 <dwd_name>/ 子目录）
```

---

### 3.4 修改 `Doris建表语句查询` Skill

#### 3.4.1 修改 `scripts/get_create_table.py`

| 行号 | 当前代码 | 修改为 |
|------|---------|--------|
| L30 | `DEFAULT_OUT = PROJECT_ROOT / "output" / "Doris建表语句查询" / "结果"` | `DEFAULT_OUT = None` |
| L91 | `output_dir = Path(args.output_dir) if args.output_dir else DEFAULT_OUT` | 增加检查：若无 `--output-dir` 则报错 |

#### 3.4.2 修改 `SKILL.md`

| 位置 | 当前描述 | 修改为 |
|------|---------|--------|
| L23 | `默认目录 output/Doris建表语句查询/结果/` | 改为 `必须通过 --output-dir 指定目录` |

---

### 3.5 修改 `DWD字段信息Excel生成` Skill

#### 3.5.1 修改 `SKILL.md`

| 位置 | 当前描述 | 修改为 |
|------|---------|--------|
| L23 | `单独运行时：output/DWD字段信息Excel生成/<dwd>/` | 改为 `单独运行时：定位 DWD开发产物 子项目的 03_代码程序_v*/<dwd>/` |
| L27 | `output/1对1DWD单表SQL生成/<dwd>/<dwd>.sql` | 改为 `DWD开发产物子项目的 03_代码程序_v*/<dwd>/<dwd>.sql` |
| L30 | 同上 | 同上 |

**新增与 3.3.2 相同的前置步骤**：先定位 DWD 开发产物子项目。

---

### 3.6 修改 `ODS-DWD-一键生成` Skill

#### 3.6.1 修改 `SKILL.md`

| 位置 | 当前描述 | 修改为 |
|------|---------|--------|
| L15 | `output/ODS-DWD-一键生成/<dwd>/` | 改为 `<DWD开发产物子项目>/03_代码程序_v*/<dwd>/` |
| L35 | `OUTPUT_DIR = output/ODS-DWD-一键生成/<dwd>/` | 改为 `OUTPUT_DIR = <DWD开发产物>/03_代码程序_v*/<dwd>/` |

**编排器第 1 步改为**：

```markdown
1. **定位 DWD 开发产物子项目，确定统一输出目录**
   - 扫描 output/ 下是否存在含 "DWD开发产物" 的子项目
   - 若不存在 → 调用子项目管理 Skill 创建
   - 对子项目执行版本控制备份（MINOR）
   - OUTPUT_DIR = <子项目>/03_代码程序_v*/<dwd_name>/
```

---

### 3.7 修复全局知识地图

**操作**：在 `.memory/全局知识地图.md` 表格中补录缺失条目

| 需补录 | 说明 |
|--------|------|
| `00_系统治理_v1.1.0` | 框架体检已报 FAIL |
| `01_DWD开发产物_v1.0.0` | 新建子项目 |

**备份**：修改前对 `.memory/全局知识地图.md` 执行 MEMORY 模式备份

---

### 3.8 修复对话记录

| 操作 | 文件 |
|------|------|
| 删除 | `.memory/对话记录/1对1DWD单表SQL生成.md`（不合规文件名） |
| 新建 | `.memory/对话记录/01_DWD开发产物_v1.0.0.md`（标准格式，迁入有效历史） |

---

## 四、执行顺序

| 步骤 | 动作 | 涉及的 Skill |
|------|------|-------------|
| 1 | 创建 `01_DWD开发产物_v1.0.0` 子项目 | 子项目管理 |
| 2 | 迁移现有产物、删除不合规文件夹 | 手动操作 |
| 3 | 修改 `generate_dwd_sql.py`（去除默认路径） | — |
| 4 | 修改 `get_create_table.py`（去除默认路径） | — |
| 5 | 备份 4 个 Skill 文件夹 → 修改 SKILL.md | 版本控制备份 |
| 6 | 修复全局知识地图 | 版本控制备份 + 记忆管理 |
| 7 | 修复对话记录（删除旧 + 创建新） | 记忆管理 |
| 8 | 更新 `00_系统治理_v1.1.0` 的目录.md 和版本记录.md | — |
| 9 | 运行框架体检验证 | 框架体检 |

---

## 五、验证计划

### 5.1 框架体检

```powershell
powershell -ExecutionPolicy Bypass -File ".agents\skills\框架体检\scripts\framework-check.ps1"
```

期望结果：全部 PASS

### 5.2 手动验证

- [ ] `output/` 下无不合规文件夹
- [ ] `01_DWD开发产物_v1.0.0/03_代码程序/` 下有迁入的 DWD 产物
- [ ] `.memory/对话记录/` 下无 `1对1DWD单表SQL生成.md`
- [ ] `.memory/全局知识地图.md` 含 `00_系统治理` 和 `01_DWD开发产物` 条目
- [ ] 4 个 Skill 的 SKILL.md 均已更新输出路径描述
- [ ] 2 个 Python 脚本不传 `--output-dir` 时报错而非默认写入 output/

---

## 六、风险与注意事项

> [!WARNING]
> 修改 `.py` 脚本不受 BOM 约束，可直接用编辑工具。但修改 SKILL.md 时注意不要破坏 YAML frontmatter 格式。

> [!IMPORTANT]
> 编排器 `ODS-DWD-一键生成` 在调用子 Skill 前需要先定位子项目。这引入了对子项目管理 Skill 的依赖链，如果 AI 切换会话后忘记定位子项目，脚本会直接报错——这是**有意设计**的 fail-safe 行为。

> [!NOTE]
> `DWD字段信息Excel生成` 的 `SKILL.md` L27 和 L30 硬编码了读取 DWD SQL 的路径 `output/1对1DWD单表SQL生成/<dwd>/`，这不是输出路径而是**输入路径**。修改后需要改为从 DWD 开发产物子项目中定位 SQL 文件。
