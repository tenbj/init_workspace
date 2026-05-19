---
name: B02_版本控制备份
description: 修改 live 文件前必须使用；按目标类型备份到 .history，并维护 output/.memory 版本状态。
---

# 版本控制备份技能（File Version Control Backup）

## 何时使用此技能

**每次修改任何文件之前，无一例外**，必须执行此技能。包括但不限于：
- 修改文档内容
- 调整文件结构
- 补充或删除任何内容

---

## 核心流程（每次修改文件前必须完整执行）

### 第 1 步：判断目标类型，选择对应模式

根据要修改的文件/文件夹路径，确定备份模式：

| 目标路径 | 备份模式 | `-Mode` 参数 | 原文件/文件夹处理 |
|---------|---------|-------------|-----------------|
| `output/` 下的子项目文件夹 | PROJECT | 省略（AUTO 自动识别） | 旧版本快照进 `.history`（版本号 + 时间戳后缀），live 文件夹**保持稳定** |
| `.agents/rules/` 下的配置文件 | CONFIG | `-Mode CONFIG` | **保持不变** |
| 根目录独立文件（如 `AGENTS.md`、`CLAUDE.md`、`README.md`） | CONFIG | `-Mode CONFIG` | **保持不变**，备份到 `.history/{文件主名}/` |
| `.agents/skills/` 下的 Skill 文件夹 | FOLDER | `-Mode FOLDER` | **保持不变** |
| `.system/` 下的子文件夹 | FOLDER | `-Mode FOLDER` | **保持不变**，并追加 `.history/.system/更新日志.md` |
| `.memory/知识提炼/*.md`、`.memory/全局知识地图.md` | MEMORY | `-Mode MEMORY` 或 AUTO 自动识别 | **保持稳定文件名**，旧版本写入 `.history/.memory/` |

> **PROJECT 模式是 output/ 下唯一合法的备份模式**。不再支持 output/ 下逐文件的 FILE 模式。

> **路径防线（强制）**：
>
> - 默认在当前项目根目录执行备份命令，`-File` 与 `-TargetPath` 都优先使用项目内相对路径。
> - 禁止手工 `Copy-Item` / `Move-Item` / `New-Item` 到 `.history`，也禁止 AI 自行拼接 `.history` 路径。
> - `.agents/skills/{Skill名}` 的唯一合法快照位置是 `.history/.agents/skills/{Skill名}_{yyyyMMddHHmmss}/`。
> - 看到 `.history/skills/`、`.history/rules/` 这类少了上级镜像层的路径，立即视为错误，不得继续修改文件。

> **MEMORY 模式目标必须是当前态稳定文件**：文件名不能带 `_v*`。例如应操作 `.memory/知识提炼/版本管理.md`，不得操作 `.memory/知识提炼/版本管理_v1.0.0.md`；应操作 `.memory/全局知识地图.md`，不得操作 `.memory/全局知识地图_v1.2.0.md`。

> **不使用备份脚本的路径**：
>
> - `.memory/对话记录/`
> - `.memory/系统记录/`
> - `.memory/` 下任何 `*_v*.md` 历史副本
>
> 这两类文件是追加型记忆，直接原地追加，不做版本备份。
> 带 `_v*` 的 `.memory` 文件若出现在当前区，是待整理的历史副本，不是可继续编辑的 live 文件。

> **子项目版本 vs live 路径**：子项目 live 文件夹保持 `{编号}_{主题}` 稳定命名（如 `05_工作区初始化工具`）。整体版本写入 `版本记录.md`，历史快照名携带备份时版本号。修改子项目内任何文件前，都应对整个子项目文件夹执行 PROJECT 备份。

> **PROJECT 模式额外需要 `-ChangeType`**，根据本次修改幅度选择：
>
> | 变更类型 | 参数值 | 使用场景 |
> |--------|--------|---------|
> | 大版本 | `MAJOR` | 内容结构、框架的不兼容重大修改 |
> | 小版本 | `MINOR` | 新增内容、新增章节，向下兼容 |
> | 补丁版本 | `PATCH` | 修复错误、微调描述、轻微补充 |

### 第 2 步：调用备份脚本

在当前项目根目录下使用 `run_command` 工具执行 PowerShell 命令，根据模式选择对应示例。项目路径经常变化时，不要写死 `E:\...` 绝对路径。

---

#### 📁 PROJECT 模式 — output/ 子项目（最常用）

整个子项目文件夹被**完整复制**到 `.history/output/`，快照名为 `{稳定子项目文件夹名}_v{备份时版本}_{yyyyMMddHHmmss}`；live 文件夹名称不变。`版本记录.md` 自动追加新版本条目。

```powershell
powershell -ExecutionPolicy Bypass -File ".agents\skills\B02_版本控制备份\scripts\backup.ps1" `
    -TargetPath "output\<子项目文件夹>" `
    -ChangeType <MAJOR|MINOR|PATCH>
```

**示例**（对 05 子项目做 MINOR 备份）：
```powershell
powershell -ExecutionPolicy Bypass -File ".agents\skills\B02_版本控制备份\scripts\backup.ps1" `
    -TargetPath "output\05_工作区初始化工具" `
    -ChangeType MINOR
```

执行结果：live 文件夹仍为 `05_工作区初始化工具`，快照 `05_工作区初始化工具_v1.2.0_20260504023015` 进 `.history/output/`，`版本记录.md` 顶部新增 v1.3.0 条目。

---

#### ⚙️ CONFIG 模式 — 配置文件与根目录独立文件

原文件**保持不变**，仅在 `.history/` 复制一份带时间戳的备份。`.agents/rules/` 按镜像路径进入 `.history/.agents/rules/`；根目录独立文件统一进入 `.history/{文件主名}/`，例如 `README.md` 进入 `.history/README/README_{yyyyMMddHHmmss}.md`，`AGENTS.md` 进入 `.history/AGENTS/AGENTS_{yyyyMMddHHmmss}.md`。

```powershell
powershell -ExecutionPolicy Bypass -File ".agents\skills\B02_版本控制备份\scripts\backup.ps1" `
    -TargetPath ".agents\rules\<规则文件名>" `
    -Mode CONFIG
```

```powershell
powershell -ExecutionPolicy Bypass -File ".agents\skills\B02_版本控制备份\scripts\backup.ps1" `
    -TargetPath "AGENTS.md" `
    -Mode CONFIG
```

---

#### 📁 FOLDER 模式 — .agents/skills/ Skill 文件夹或 .system/ 子文件夹

整个 Skill 文件夹或 `.system/` 子文件夹被**快照**到 `.history/`（带时间戳），原文件夹**保持不变**。例如 `.system/standards/` 会备份到 `.history/.system/standards_{yyyyMMddHHmmss}/`。

`.system/` 子文件夹备份成功后，脚本会自动追加 `.history/.system/更新日志.md`，以 `文件夹_时间戳` 为标题记录：

- 备份时间、源路径、快照路径
- 快照内每个文件的相对路径
- 备份时识别到的版本
- 修改后版本与变更内容占位，修改完成后必须补全

```powershell
powershell -ExecutionPolicy Bypass -File ".agents\skills\B02_版本控制备份\scripts\backup.ps1" `
    -TargetPath ".agents\skills\<Skill名>" `
    -Mode FOLDER
```

---

#### 🧠 MEMORY 模式 — .memory 的版本化文件

适用于：

- `.memory/知识提炼/{话题名}.md`
- `.memory/全局知识地图.md`

当前文件名**保持不变**，旧版本写入 `.history/.memory/`。

```powershell
powershell -ExecutionPolicy Bypass -File ".agents\skills\B02_版本控制备份\scripts\backup.ps1" `
    -TargetPath ".memory\知识提炼\<话题名>.md" `
    -Mode MEMORY `
    -ChangeType <MAJOR|MINOR|PATCH>
```

---

### 第 3 步：读取脚本输出，确认备份结果

脚本执行成功后，输出示例如下：

**PROJECT 模式输出示例：**
```
[OK] History snapshot: ...\05_工作区初始化工具_v1.2.0_20260504023015
[OK] Version record updated: ...\05_工作区初始化工具\版本记录.md
==========================================
  Project Backup Complete
==========================================
  Source    : ...\05_工作区初始化工具
  Snapshot  : ...\05_工作区初始化工具_v1.2.0_20260504023015
  Live Path : ...\05_工作区初始化工具
  Version   : v1.2.0 --> v1.3.0 (MINOR)
==========================================
```

**FOLDER 模式输出示例：**
```
[OK] Skill folder snapshot created: .history\.agents\skills\B02_版本控制备份_202605031718
==========================================
  Folder Snapshot Complete
==========================================
  Source   : .agents\skills\B02_版本控制备份
  Snapshot : .history\.agents\skills\B02_版本控制备份_202605031718
==========================================
```

**CONFIG 模式输出示例：**
```
[OK] Config file backed up: .history\.agents\rules\version-control-rules_202605031718.md
==========================================
  Config Backup Complete
==========================================
  Source : .agents\rules\version-control-rules.md
  Backup : .history\.agents\rules\version-control-rules_202605031718.md
==========================================
```

**MEMORY 模式输出示例：**
```
[OK] Memory snapshot created: .history\.memory\全局知识地图\全局知识地图_v1.2.0.md
[OK] Live memory file kept stable: .memory\全局知识地图.md
==========================================
  Memory Backup Complete
==========================================
  Source    : .memory\全局知识地图.md
  Snapshot  : .history\.memory\全局知识地图\全局知识地图_v1.2.0.md
  Live File : .memory\全局知识地图.md
  Version   : v1.2.0 --> v1.3.0 (MINOR)
==========================================
```

### 第 4 步：在正确的目标文件上进行修改

| 模式 | 备份后在哪里修改 |
|------|---------------|
| PROJECT | 原稳定子项目文件夹（如 `05_工作区初始化工具/`）内的文件 |
| CONFIG | 原文件（如 `version-control-rules.md`，名称不变） |
| FOLDER | 原 Skill 文件夹内的文件（文件夹名称不变） |
| MEMORY | 原文件（如 `.memory/全局知识地图.md`，名称不变） |

⚠️ 不得修改 `.history` 目录中的任何备份文件。

### 第 5 步：更新版本记录

- `PROJECT` 模式：脚本已自动在 `版本记录.md` 顶部追加条目。需要手动填写本次的**变更描述**和**子文件变更明细**。
- `MEMORY` 模式：在当前稳定文件中继续修改内容，并同步更新文末版本记录或相关说明。

`版本记录.md` 条目格式：
```markdown
## v1.3.0 (2026-05-04 02:30:15)

**变更类型**：MINOR
**变更描述**：{手动填写}

**子文件变更明细**：

| 文件 | 版本变更 | 变更描述 |
|------|---------|---------|
| `src/初始化工作区.py` | v1.1.0 → v1.2.0 | {手动填写} |

---
```

---

## 目录结构说明

```
<当前项目根>\
├── output\                                  ← 当前工作文件
│   └── 05_工作区初始化工具\                  ← PROJECT 模式：稳定 live 文件夹
│       ├── 版本记录.md                       ← 子项目版本变更历史
│       └── ...
├── .agents\
│   ├── rules\
│   │   └── version-control-rules.md         ← CONFIG 模式：原文件名不变
│   └── skills\
│       └── 版本控制备份\                     ← FOLDER 模式：原文件夹不变
├── .memory\
│   ├── 知识提炼\
│   │   └── 版本管理.md                       ← MEMORY 模式：当前态稳定文件名
│   └── 全局知识地图.md                       ← MEMORY 模式：当前态稳定文件名
└── .history\                                 ← 备份目录（镜像结构）
    ├── output\
    │   └── 05_工作区初始化工具_v1.2.0_20260504023015\   ← PROJECT 历史快照（版本号+时间戳）
    ├── README\
    │   └── README_202605031718.md                    ← 根目录独立文件备份
    ├── .system\
    │   ├── 更新日志.md                                ← .system 快照更新日志
    │   └── standards_202605031718\                    ← .system 子文件夹快照
    ├── .agents\
    │   ├── rules\
    │   │   └── version-control-rules_202605031718.md    ← CONFIG 备份（时间戳）
    │   └── skills\
    │       └── B02_版本控制备份_202605031718\               ← FOLDER 快照（时间戳）
    └── .memory\
        ├── 知识提炼\
        │   └── 版本管理_v1.0.0.md                       ← MEMORY 历史版本
        └── 全局知识地图\
            └── 全局知识地图_v1.2.0.md                   ← MEMORY 历史版本
```

---

## 文件/文件夹命名规则

- **子项目 live 文件夹**：`{编号}_{主题}`，例如 `05_工作区初始化工具`
- **子文件**：`{两位编号}_{标题}.{扩展名}`，例如 `01_减肥核心理论.md`；需要版本时写入正文元数据或 `版本记录.md`
- `.history/` 中子项目历史快照：`{编号}_{主题}_v{x.y.z}_{yyyyMMddHHmmss}`，例如 `05_工作区初始化工具_v1.2.0_20260504023015`
- `.agents/rules/` 与 `.agents/skills/` 的备份仍使用时间戳
- 根目录独立文件备份：`.history/{文件主名}/{文件主名}_{yyyyMMddHHmmss}{扩展名}`，例如 `.history/README/README_20260512010101.md`
- `.system/` 子文件夹快照：`.history/.system/{子文件夹名}_{yyyyMMddHHmmss}/`，并同步追加 `.history/.system/更新日志.md`
- `.memory` 当前态文件不带版本号，版本号只保留在文件头隐藏注释和 `.history/.memory/` 的历史文件名中

---

## 错误处理

| 错误信息 | 原因 | 解决方法 |
|---------|------|---------|
| `Target not found` | 文件/文件夹路径有误 | 检查路径是否正确 |
| `Workspace root not found` | 项目根目录没有 `.history` 文件夹 | 在项目根目录手动创建 `.history` 文件夹 |
| `output/ files must be backed up via PROJECT mode` | 尝试对 output/ 下的单个文件使用备份 | 改为对父级子项目文件夹使用 PROJECT 模式 |
| `FOLDER mode only supports one .agents/skills/<skill> folder or one .system/<folder>` | 试图备份 `.agents/skills` 总目录或其他非白名单文件夹 | 改为对单个 Skill 文件夹或 `.system` 子文件夹执行 FOLDER |
| `Target escapes workspace root` | 传入路径越出了当前项目根目录 | 改用当前项目内相对路径 |

---

## 禁止行为

- ❌ 在未执行备份脚本的情况下直接修改文件
- ❌ 修改 `.history` 目录中的备份文件
- ❌ 手工创建、复制或移动任何内容到 `.history` 作为备份；备份必须由 `backup.ps1` 生成
- ❌ 把 `.agents/skills/` 的快照放到 `.history/skills/`，正确位置必须是 `.history/.agents/skills/`
- ❌ 跳过版本号判断，任意指定版本类型
- ❌ 对 output/ 下的单个文件使用 FILE 模式（必须对整个子项目文件夹用 PROJECT 模式）
- ❌ 对 `.agents/rules/` 或 `.agents/skills/` 使用 PROJECT/FILE 模式
- ❌ 对 `.memory/对话记录/` 或 `.memory/系统记录/` 使用备份脚本
- ❌ 对 `.memory/` 当前区中带 `_v*` 的历史副本使用 MEMORY 模式
- ❌ 对 `.memory/` 目录做整目录快照
- ❌ 用 Trae Write / SearchReplace 工具修改本 Skill 的 `backup.ps1` 脚本（见下方编码约束）

---

## .ps1 脚本编码约束

> `workspace-spec.json` 中 `bomCheck.files` 列出的所有 `.ps1` 必须保持 UTF-8 with BOM。Trae Write/SearchReplace 会破坏 BOM，导致中文乱码。

修改这些 `.ps1` 时，必须通过 ASCII-only 临时脚本或 RunCommand 调用 `[System.IO.File]::WriteAllText(path, content, [System.Text.UTF8Encoding]::new($true))` 写入。被破坏时通过读写 API 恢复 BOM。

详见 `version-control-rules.md` 中的「.ps1 脚本编码约束」章节。
