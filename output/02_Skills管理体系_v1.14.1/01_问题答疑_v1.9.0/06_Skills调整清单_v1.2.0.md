# Skills 调整清单

> 基于当前 `.agents/skills` 实际目录、`Skills 管理标准` 和路径引用扫描结果，整理需要迁移的 Skill 本体与系统引用。

---

## 结论

当前 15 个本地 Skill 全部需要调整。原因是新标准要求文件夹名与 YAML `name` 均采用：

```text
{域代码}{编号}_{技能名}_v{MAJOR}.{MINOR}.{PATCH}
```

当前状态下，没有任何一个 Skill 同时满足“域编号 + 技能名 + 三段式版本号 + YAML name 同步带版本号”。

复核后确认，迁移影响面不只包括 Skill 本体和 `workspace-spec.json`，还包括规则文件、标准文件、脚本 fallback、`agents/openai.yaml`、references 示例路径，以及部分业务输出目录口径。

---

## Skill 本体调整清单

| 域 | 当前文件夹 | 当前 YAML name | 目标文件夹 | 目标 YAML name | 调整级别 |
|---|---|---|---|---|---|
| A | `创建技能` | `创建技能` | `A01_创建技能_v1.0.0` | `A01_创建技能_v1.0.0` | 重命名 + 改 name |
| A | `安装技能` | `安装技能` | `A02_安装技能_v1.0.0` | `A02_安装技能_v1.0.0` | 重命名 + 改 name |
| B | `框架体检` | `框架体检` | `B01_框架体检_v1.0.0` | `B01_框架体检_v1.0.0` | 重命名 + 改 name + 脚本路径 |
| B | `版本控制备份` | `版本控制备份` | `B02_版本控制备份_v1.0.0` | `B02_版本控制备份_v1.0.0` | 重命名 + 改 name + 脚本路径 |
| B | `记忆管理` | `记忆管理` | `B03_记忆管理_v1.0.0` | `B03_记忆管理_v1.0.0` | 重命名 + 改 name + 脚本路径 |
| B | `子项目管理` | `子项目管理` | `B04_子项目管理_v1.0.0` | `B04_子项目管理_v1.0.0` | 重命名 + 改 name + 脚本路径 |
| B | `课题研究` | `课题研究` | `B05_课题研究_v1.0.0` | `B05_课题研究_v1.0.0` | 重命名 + 改 name |
| B | `项目规范化` | `项目规范化` | `B06_项目规范化_v1.0.0` | `B06_项目规范化_v1.0.0` | 重命名 + 改 name + 脚本路径 |
| C | `01_同步代码仓库_v1.0` | `01_同步代码仓库_v1.0` | `C01_同步代码仓库_v1.0.0` | `C01_同步代码仓库_v1.0.0` | 旧格式修正 |
| C | `数仓生产库查询` | `数仓生产库查询` | `C02_数仓生产库查询_v1.0.0` | `C02_数仓生产库查询_v1.0.0` | 重命名 + 改 name |
| C | `Doris建表语句查询` | `Doris建表语句查询` | `C03_Doris建表语句查询_v1.0.0` | `C03_Doris建表语句查询_v1.0.0` | 重命名 + 改 name |
| C | `临时数据存储` | `临时数据存储` | `C04_临时数据存储_v1.0.0` | `C04_临时数据存储_v1.0.0` | 重命名 + 改 name |
| C | `1对1DWD单表SQL生成` | `1对1DWD单表SQL生成` | `C05_1对1DWD单表SQL生成_v1.0.0` | `C05_1对1DWD单表SQL生成_v1.0.0` | 重命名 + 改 name |
| C | `DWD字段信息Excel生成` | `DWD字段信息Excel生成` | `C06_DWD字段信息Excel生成_v1.0.0` | `C06_DWD字段信息Excel生成_v1.0.0` | 重命名 + 改 name |
| C | `ODS-DWD-一键生成` | `ODS-DWD-一键生成` | `C07_ODS-DWD-一键生成_v1.0.0` | `C07_ODS-DWD-一键生成_v1.0.0` | 重命名 + 改 name |

---

## 系统引用调整清单

### `workspace-spec.json`

| 配置项 | 当前状态 | 目标 |
|---|---|---|
| `overwriteLayer.skills` | 仍是 `创建技能`、`子项目管理` 等旧名 | 改为 `A01_创建技能_v1.0.0`、`B04_子项目管理_v1.0.0` 等新名 |
| `bomCheck.files` | 仍指向 `.agents/skills/版本控制备份/...` 等旧路径 | 改为 `.agents/skills/B02_版本控制备份_v1.0.0/...` 等新路径 |

### `version-control-rules.md`

需要同步改 7 个 BOM 脚本路径：

| 脚本 | 目标路径 |
|---|---|
| `backup.ps1` | `.agents/skills/B02_版本控制备份_v1.0.0/scripts/backup.ps1` |
| `new_project.ps1` | `.agents/skills/B04_子项目管理_v1.0.0/scripts/new_project.ps1` |
| `next_number.ps1` | `.agents/skills/B04_子项目管理_v1.0.0/scripts/next_number.ps1` |
| `normalize_project.ps1` | `.agents/skills/B04_子项目管理_v1.0.0/scripts/normalize_project.ps1` |
| `framework-check.ps1` | `.agents/skills/B01_框架体检_v1.0.0/scripts/framework-check.ps1` |
| `normalize.ps1` | `.agents/skills/B06_项目规范化_v1.0.0/scripts/normalize.ps1` |
| `remove.ps1` | `.agents/skills/B03_记忆管理_v1.0.0/scripts/remove.ps1` |

### 其他 Rules 文件

这些规则文件虽然不一定写死路径，但写了旧 Skill 显示名或触发语义。迁移后建议同步为新编号名称，避免“标准里叫 B01，规则里仍叫框架体检”的双轨状态。

| 文件 | 当前关注点 | 目标处理 |
|---|---|---|
| `.agents/rules/direction-rules.md` | `Skill：框架体检`、`Skill：子项目管理` 等旧显示名 | 改为 `B01_框架体检_v1.0.0`、`B04_子项目管理_v1.0.0` |
| `.agents/rules/memory-rules.md` | `记忆管理`、`子项目管理`、`版本控制备份` 等旧显示名 | 改为 `B03_记忆管理_v1.0.0`、`B04_子项目管理_v1.0.0`、`B02_版本控制备份_v1.0.0` |
| `.agents/rules/filename-rules.md` | 若出现 Skill 名称或示例路径 | 按新命名规则同步 |

### 标准文件

| 文件 | 当前关注点 | 目标处理 |
|---|---|---|
| `.system/standards/workspace-spec.json` | `overwriteLayer.skills`、`bomCheck.files` | 改为新 Skill 名和新脚本路径 |
| `.system/standards/工作区骨架规格.md` | 仍写“8 个 Skill”、旧 Skill 列表、旧脚本目录表 | 更新为编号后的核心 Skill 列表和脚本目录 |
| `.system/standards/工作区命名规范.md` | 提炼来源、`.agents/skills/{Skill名}` 示例、历史快照示例仍是旧名 | 更新为新 Skill 名示例，或明确 `{Skill名}` 指编号版本全名 |
| `.system/standards/03_Skills管理标准_v1.0.0.md` | 标准本身已改为 YAML name 带版本号 | 迁移后需要校对映射表与实际目录一致 |

### 脚本内部 fallback 与检查逻辑

脚本有些路径从 `workspace-spec.json` 读取，但仍保留旧路径 fallback 或旧 Skill 名 fallback。迁移后也应同步，否则 spec 读取失败时会回落到旧结构。

| 文件 | 需要关注的内容 |
|---|---|
| `.agents/skills/框架体检/scripts/framework-check.ps1` | `$spec.overwriteLayer.skills` 读取失败时的旧 Skill 名 fallback；BOM 文件 fallback 仍是旧路径 |
| `.agents/skills/项目规范化/scripts/normalize.ps1` | `$requiredSkills` fallback 仍是旧 Skill 名；日志文本可能输出旧 `skills/<名>/` |
| `.agents/skills/版本控制备份/scripts/backup.ps1` | FOLDER 模式当前仍强调 source unchanged；若后续要自动 bump Skill 文件夹，需要扩展 `SKILL` 模式 |
| `.agents/skills/Doris建表语句查询/scripts/get_create_table.py` | 注释中含旧 skill 路径，可按需要同步 |
| `.agents/skills/1对1DWD单表SQL生成/scripts/generate_dwd_sql.py` | 注释中含旧 skill 路径，可按需要同步 |

### 交叉引用文件

以下文件中存在旧 Skill 名、旧路径或运行示例，迁移时需要一起替换：

| 文件 | 需要关注的内容 |
|---|---|
| `.agents/skills/版本控制备份/SKILL.md` | 备份脚本路径、FOLDER 模式示例、历史目录说明 |
| `.agents/skills/框架体检/SKILL.md` | `framework-check.ps1` 调用路径 |
| `.agents/skills/子项目管理/SKILL.md` | `new_project.ps1`、`next_number.ps1`、`normalize_project.ps1` 示例路径 |
| `.agents/skills/项目规范化/SKILL.md` | `normalize.ps1` 路径、标准化流程引用 |
| `.agents/skills/Doris建表语句查询/SKILL.md` | 根目录定位说明、跨 Skill 依赖 |
| `.agents/skills/DWD字段信息Excel生成/SKILL.md` | 根目录定位说明 |
| `.agents/skills/1对1DWD单表SQL生成/SKILL.md` | 子项目管理、版本控制备份等语义引用 |
| `.agents/skills/数仓生产库查询/references/加载方式.md` | `doris_query_client.py` 脚本路径 |
| `.agents/skills/临时数据存储/references/加载方式.md` | `doris_storage_client.py` 脚本路径 |
| `.agents/skills/01_同步代码仓库_v1.0/references/同步说明.md` | 同步脚本路径、旧斜杠命令 |
| `.agents/skills/*/agents/openai.yaml` | `display_name`、`default_prompt`、展示名称 |

### `agents/openai.yaml` 状态

当前 15 个 Skill 中，12 个已有 `agents/openai.yaml`，3 个缺失：

| Skill | 当前状态 | 目标处理 |
|---|---|---|
| `子项目管理` | 缺 `agents/openai.yaml` | 若标准要求所有 Skill 有展示配置，应补建 |
| `版本控制备份` | 缺 `agents/openai.yaml` | 若标准要求所有 Skill 有展示配置，应补建 |
| `记忆管理` | 缺 `agents/openai.yaml` | 若标准要求所有 Skill 有展示配置，应补建 |
| 其余 12 个 | 已有 `agents/openai.yaml` | 更新 `display_name`，必要时更新 `default_prompt` 中的斜杠命令 |

### `.claude/commands` 斜杠命令文件

复核执行时发现 `.claude/commands/` 下已经存在 15 个斜杠命令文件。若目标是“斜杠调用时也能带版本号”，命令文件名也必须跟随 Skill 文件夹名带版本号。

| 当前命令文件模式 | 目标命令文件模式 | 处理规则 |
|---|---|---|
| `{域编号}_{技能名}.md` | `{域编号}_{技能名}_v{MAJOR}.{MINOR}.{PATCH}.md` | 文件名与 Skill 文件夹名保持一致 |
| 文件内容指向旧 Skill 路径 | `请读取并执行 .agents/skills/{Skill文件夹名}/SKILL.md` | 内容路径同步到新文件夹 |
| `CLAUDE.md` 维护规则 | 说明命令文件必须带版本号 | Skill bump 后同步重命名命令文件 |

### 业务输出路径口径

部分数仓 Skill 的说明或脚本中仍使用旧的按 Skill 名输出目录，例如 `output/1对1DWD单表SQL生成/...`、`output/Doris建表语句查询/结果/...`。这类路径不一定是 Skill 调用路径，但迁移前要决定是否同步为新编号目录，或保留为业务产物目录。

| 文件 | 需要决策的内容 |
|---|---|
| `.agents/skills/1对1DWD单表SQL生成/SKILL.md` | `output/Doris建表语句查询/结果/` 是否改为新命名 |
| `.agents/skills/1对1DWD单表SQL生成/scripts/generate_dwd_sql.py` | 注释里的 `output/1对1DWD单表SQL生成/...` 是否改为新命名 |
| `.agents/skills/DWD字段信息Excel生成/references/自查清单.md` | `output/1对1DWD单表SQL生成/...` 是否改为新命名 |
| `.agents/skills/ODS-DWD-一键生成/SKILL.md` | `output/ODS-DWD-一键生成/<dwd_name>/` 是否改为新命名 |

---

## 建议迁移顺序

1. 先备份所有待改 Skill 文件夹。
2. 先改 1 个 Skill 做斜杠验证，例如 `框架体检` → `B01_框架体检_v1.0.0`。
3. 验证 `/B01` 和 `/B01_框架体检_v1.0.0` 都能命中。
4. 批量重命名 15 个 Skill 文件夹。
5. 批量更新所有 `SKILL.md` 的 YAML `name`。
6. 更新 `agents/openai.yaml`：已有则改展示名，缺失则决定是否补建。
7. 更新 `.claude/commands` 命令文件名和 `CLAUDE.md` 维护规则。
8. 更新 `workspace-spec.json`、Rules、标准文件、脚本 fallback 和交叉引用。
9. 决策业务输出目录是否跟随 Skill 新命名。
10. 跑框架体检，重点检查 `overwriteLayer.skills` 与 `bomCheck.files`。
11. 写入系统记录和 Skills 管理体系对话记录。

---

## 风险提醒

文件夹名带版本号后，每次 Skill 升级都会改路径。短期可以手动同步 `workspace-spec.json`、规则和引用；中长期建议补 `skillRegistry` 或扩展备份脚本的 `SKILL` 模式，避免每次版本 bump 都改多处路径。
