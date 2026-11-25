---
name: B02_版本控制备份
description: 按 workspace-spec.json 的 backupPolicy 在修改受保护 live 文件前执行备份并维护版本号；output 仅备份 01/02，版本化 .memory 维持现状，核心骨架 Git 托管区免备份。
---

# 版本控制备份技能（File Version Control Backup）

## SSOT 事实源

本技能的备份范围、白名单目录与免备份路径**统一以 `.system/standards/workspace-spec.json` 的 `backupPolicy` 为单一事实源（SSOT）**。`backup.ps1` 与 `B06` 的 `normalize.ps1` 均通过共享函数 `Get-WorkspaceBackupPolicy` 运行时读取同一配置，不在多处重复硬编码。

## 何时使用此技能

**需要执行 B02 的范围**（按 `backupPolicy`）：
- 修改 `output/<子项目>/01_问题答疑/` 或 `02_课题研究/` 下的任何内容（调用 `PROJECT` 模式，目标传 `output/<子项目>`）
- 修改 `.memory/知识提炼/*.md` 或 `.memory/全局知识地图.md`（调用 `MEMORY` 模式）
- 按需备份其他未免除的非秘密独立配置文件（如非 Git 托管配置或明确需要普通备份的公开配置，调用 `CONFIG` 模式）

**免除 B02 的范围（不触发、不执行备份）**：
- `output/<子项目>/03_代码程序/` 及子项目根目录其他文件（含 `目录.md`、`版本记录.md` 等）：代码程序由独立 Git 或工具链管理，改 `03_代码程序` 不触发 B02，且 `PROJECT` 快照也不会复制它们
- `.agents/skills/`、`.agents/rules/`、`.system/`：已纳入核心骨架 Git 仓库管理，修改前走 `B11` 工作分支保护，不执行 B02 备份（`.history/` 下对应目录仅保留既有历史归档）
- `.memory/对话记录/`、`.memory/系统记录/`、`.memory/任务进度/`：追加型 / `B08` 运行态记忆，直接写入不做版本备份
- `.envs/` 中的真实私有凭据（走 `B12` 专用加密保护）

---

## 快照安全与边界

- **白名单范围（`PROJECT`）**：`backup.ps1` 按 `backupPolicy.project.includeSubfolders` 仅遍历并复制 `01_问题答疑/` 与 `02_课题研究/`；不进入也不复制 `03_代码程序/` 及子项目根目录其他文件。`B06` 的规范化前置快照复用同一 SSOT 策略函数。
- **凭据保护预检**：在纳入快照的目录树内，拒绝复制 `.env`/`*.env`，并拒绝 `.envs/` 中白名单外文件、目录或非空示例。先拒绝整个备份，不静默跳过凭据后宣称完整。
- **Git 元数据边界**：在纳入快照的目录树内，各层递归排除名为 `.git` 的目录或文件；不使用 `.gitignore` 过滤，实际工作文件与空目录均保留。
- **符号链接/junction 保护**：不跟随符号链接或 junction；纳入快照的目录树或来源/目标祖先路径出现链接即停止。`.git` 链接直接排除。
- **失败保护**：枚举或复制失败立即停止，保留 `.incomplete-<guid>` 诊断目录，不更新 live 版本、不覆盖已有快照。

---

## 核心流程

### 第 1 步：对照 `backupPolicy` 判断目标与模式

| 目标路径 | 是否走 B02 | 模式 | 备份落点与 live 处理 |
|---------|-----------|------|---------------------|
| `output/<子项目>`（修改 `01_问题答疑` / `02_课题研究` 时） | **是** | `PROJECT`（`AUTO` 自动识别） | 仅复制 `01_问题答疑/` 与 `02_课题研究/` 至 `.history/output/{稳定名}_v{旧版本}_{yyyyMMddHHmmss}/`；live 目录名稳定，`版本记录.md` 自动追加新版本 |
| `.memory/知识提炼/*.md`、`.memory/全局知识地图.md` | **是** | `MEMORY`（`AUTO` 自动识别） | live 文件名保持稳定无版本号，旧版写入 `.history/.memory/`，文件头 `<!-- memory-version: x.y.z -->` 递增 |
| `output/<子项目>/03_代码程序/` 及非 `01`/`02` 根文件 | **否（免除）** | — | 不触发 B02，不复制进快照，不修改 `版本记录.md` |
| `.agents/skills/`、`.agents/rules/`、`.system/` | **否（免除）** | — | 由核心骨架 Git 管理（走 `B11` 工作分支）；`.history/` 对应目录仅保留既有历史归档 |
| `.memory/对话记录/`、`.memory/系统记录/`、`.memory/任务进度/` | **否（免除）** | — | 追加型 / 运行态，直接写入 |
| 其他未免除非秘密独立文件（如 `.envs/catalog.json`） | 按需 | `CONFIG` | 原文件不变，按时间戳复制至 `.history/` |

> **路径防线（强制）**：
> - 默认在项目根目录执行命令，`-TargetPath` 使用项目内相对路径。
> - 禁止手工 `Copy-Item` / `Move-Item` / `New-Item` 到 `.history`，禁止 AI 自行拼接 `.history` 路径。
> - `MEMORY` 模式只能作用于当前态稳定文件（文件名不得带 `_v*`）。
> - `PROJECT` 模式需要指定 `-ChangeType`：`MAJOR`（不兼容框架变更）/ `MINOR`（新增章节或内容）/ `PATCH`（修正错误或微调）。

### 第 2 步：调用备份脚本

#### 📁 PROJECT 模式 — `output/` 子项目（仅备份 `01_问题答疑` 与 `02_课题研究`）

```powershell
powershell -ExecutionPolicy Bypass -File ".agents\skills\B02_版本控制备份\scripts\backup.ps1" `
    -TargetPath "output\<子项目文件夹>" `
    -ChangeType <MAJOR|MINOR|PATCH>
```

执行结果：live 文件夹名保持稳定，`.history/output/{稳定名}_v{旧版本}_{yyyyMMddHHmmss}/` 仅包含 `01_问题答疑/` 与 `02_课题研究/`，live `版本记录.md` 顶部追加新版本条目。

#### PROJECT 完整快照发布恢复

仅当完整复制已结束、最终目录发布失败而留下 `.incomplete-<guid>` 时，保持源目录停止写入，向同一官方脚本传 `-ResumeSnapshotPath <失败输出中的原路径>`，保留原 `-TargetPath` 与 `-ChangeType`：

- 仅接受本工作区 `.history/output/` 直属、属于当前项目与当前版本、携带原时间戳和 GUID 的候选；拒绝已有最终目录及链接。
- 源树按 `backupPolicy.project.includeSubfolders`（`01_问题答疑`、`02_课题研究`）并排除各层 `.git` 计算清单；待发布候选做全树核对（禁止夹带 `03_代码程序`、子项目根文件或 `.git`）。两边集合、文件长度与 SHA256 必须完全一致，并二次复核源树未变后再发布，成功后更新 live `版本记录.md`。
- 合成回归：`python .agents/skills/B02_版本控制备份/tests/test_resume_snapshot.py`（只在系统临时目录构造工作区）。

#### 🧠 MEMORY 模式 — `.memory/` 版本化文件（维持现状）

```powershell
powershell -ExecutionPolicy Bypass -File ".agents\skills\B02_版本控制备份\scripts\backup.ps1" `
    -TargetPath ".memory\知识提炼\<话题名>.md" `
    -Mode MEMORY `
    -ChangeType <MAJOR|MINOR|PATCH>
```

#### ⚙️ CONFIG 模式 — 未免除的非秘密独立文件（按需）

```powershell
powershell -ExecutionPolicy Bypass -File ".agents\skills\B02_版本控制备份\scripts\backup.ps1" `
    -TargetPath "<相对路径>" `
    -Mode CONFIG
```

> 注：`.agents/rules/` 与 `.system/` 已列入 `backupPolicy` 免备份范围，传入脚本会被按 SSOT 策略拦截。

### 第 3 步：确认输出并修改 live 文件

- `PROJECT` 模式：确认快照已创建且 `Scope` 与 `backupPolicy` 一致后，修改 live 子项目中的 `01_问题答疑/` 或 `02_课题研究/`，并补全 `版本记录.md` 中的变更描述与子文件明细。
- `MEMORY` 模式：在原稳定文件中继续编辑。
- 不得修改 `.history/` 中的任何备份或归档文件。

---

## 常见报错说明

| 错误信息 | 原因 | 解决方法 |
|---------|------|---------|
| `Target '...' is exempt from B02 backup per workspace-spec.json backupPolicy` | 目标属于免备份路径（如 `03_代码程序`、`.agents/skills`、`.agents/rules`、`.system`、追加型 `.memory`） | 直接按 Git/B11 或正常流程操作，无需跑 B02 |
| `output/ content under '...' must be backed up via PROJECT mode on the parent subproject folder` | 对 `01_问题答疑` / `02_课题研究` 内部单个文件或子目录直接跑了脚本 | 改为对父级 `output/<子项目>` 执行 `PROJECT` 模式 |
| `Snapshot source does not contain any configured backup subdirectories` | 目标子项目缺少 `01_问题答疑` 与 `02_课题研究` 目录 | 先检查子项目目录结构（必要时执行 `B04` 或 `B06`） |
| `Target escapes workspace root` | 路径越出当前工作区根 | 改用当前项目内相对路径 |

---

## 禁止行为

- ❌ 修改 `output/<子项目>/01_问题答疑`、`02_课题研究` 或版本化 `.memory/` 前跳过 B02
- ❌ 修改 `.history/` 目录中的备份或历史归档文件
- ❌ 手工创建、复制或移动任何内容到 `.history/` 作为备份（必须由 `backup.ps1` 生成）
- ❌ 对 `output/` 下单个文件使用 `FILE` 模式，或对 `.memory/` 做整目录快照
- ❌ 对 `.memory/` 当前区中带 `_v*` 的历史副本使用 `MEMORY` 模式
- ❌ 无视 `workspace-spec.json` 的 `backupPolicy` 在脚本或文档中另造一套备份白名单
- ❌ 用无 BOM 工具直接写回 `bomCheck.files` 列表中的 `.ps1` 文件（见下方编码约束）

---

## .ps1 脚本编码约束

> `workspace-spec.json` 中 `bomCheck.files` 列出的 `.ps1`（含 `backup.ps1`）必须保持 **UTF-8 with BOM**，避免 Windows PowerShell 5.1 按 ANSI 解码中文乱码。

修改这些 `.ps1` 时，必须通过 `[System.IO.File]::WriteAllText(path, content, [System.Text.UTF8Encoding]::new($true))` 或 Python `encoding="utf-8-sig"` 写回并校验 BOM 字节头（`EF BB BF`）。详见 `.agents/rules/version-control-rules.md`。
