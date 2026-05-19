---
trigger: always_on
---

> ⚠️ **强制门：版本控制 — 对 output/ 或 .agents/ 下的文件执行任何增、删、改操作（Write/SearchReplace/WriteAllText/新建/删除）之前，必须先执行版本控制备份。备份未完成 = 操作不允许。不得省略、不得事后补、不得因增删改幅度小跳过。**

所有 output/ 下的文件在每次增、删、改前，必须先执行版本控制备份。
具体执行步骤参考并调用 Skill：`B02`

备份必须由 `.agents/skills/B02_版本控制备份/scripts/backup.ps1` 生成，禁止 AI 或人工手工 `Copy-Item` / `Move-Item` / `New-Item` 到 `.history`，也禁止自行拼接 `.history` 路径。项目路径可能变化，调用脚本时优先使用当前项目内相对路径。

例外与补充：

- output/ 下的子项目文件夹使用 PROJECT 模式：
  - live 文件夹命名：`{编号}_{主题}`
  - 备份：整个文件夹快照到 `.history/output/{稳定文件夹名}_v{x.y.z}_{yyyyMMddHHmmss}/`，live 文件夹名称保持不变
  - 每个子项目内含 `版本记录.md`，记录整体版本变更历史和子文件变更明细
  - 每个子项目内含 `目录.md`，作为子项目内文件索引。`目录.md` 随子项目文件夹整体快照备份，不单独备份。
  - 子项目版本号由 `版本记录.md` 维护，历史快照名携带备份时版本号
  - `.memory/对话记录/{稳定子项目文件夹名}.md` 保持稳定文件名，不随版本变更改名
- `.agents/rules/` 下的配置文件，只做 `.history` 备份，文件名不带版本号
- `.agents/skills/` 下的 Skill 文件夹，只做 `.history` 快照，原文件夹名称不变
  - 唯一合法落点：`.history/.agents/skills/{Skill名}_{yyyyMMddHHmmss}/`
  - `.history/skills/` 属于错误路径，发现后必须停止修改并先纠偏
- `.memory/对话记录/` 与 `.memory/系统记录/` 是追加型记忆，不做版本备份
- `.memory/知识提炼/` 与 `.memory/全局知识地图.md` 使用 `MEMORY` 模式：
  - 当前文件名保持稳定，不在 `.memory/` 中堆多个 `v*` 文件
  - 历史版本统一写入 `.history/.memory/`
- 禁止对 `.memory/` 目录本身做整目录快照
- 禁止对 output/ 下的单个文件使用 FILE 模式（已废弃）

---

## .ps1 脚本编码约束

**所有 `.agents/` 下的 `.ps1` 脚本文件必须保持 UTF-8 with BOM 编码。**

### 为什么

Windows PowerShell 5.1 读取 `.ps1` 文件时，若文件无 BOM，则按系统默认 ANSI 代码页（中文 Windows 为 GBK/CP936）解析字节流。脚本中的中文字符会被错误解释为乱码。

### 禁止行为

- ❌ 用 Trae Write / SearchReplace 工具修改含中文的 `.ps1` 文件（这些工具保存为 UTF-8 No BOM）
- ❌ 在 `param()` 块之前放置任何可执行代码（含 `chcp 65001`）
- ❌ 用 RunCommand 的内联 PowerShell 操作 `.ps1` 文件中的中文（`$null`/`$false`/`$true` 会被外层 shell 展开）

### 正确做法

修改 `.ps1` 文件时，通过临时 ASCII-only 脚本或 RunCommand 调用 `[System.IO.File]` API：

```powershell
[System.IO.File]::WriteAllText(
    $path,
    $content,
    [System.Text.UTF8Encoding]::new($true)   # $true = with BOM
)
```

### 补救措施

若 `.ps1` 文件已被 Write/SearchReplace 破坏（BOM 丢失），通过上述 API 读写一次即可恢复 BOM：
```powershell
$c = [System.IO.File]::ReadAllText($path)
[System.IO.File]::WriteAllText($path, $c, [System.Text.UTF8Encoding]::new($true))
```

### 影响范围

| 脚本 | 路径 |
|------|------|
| `backup.ps1` | `.agents/skills/B02_版本控制备份/scripts/backup.ps1` |
| `new_project.ps1` | `.agents/skills/B04_子项目管理/scripts/new_project.ps1` |
| `next_number.ps1` | `.agents/skills/B04_子项目管理/scripts/next_number.ps1` |
| `normalize_project.ps1` | `.agents/skills/B04_子项目管理/scripts/normalize_project.ps1` |
| `framework-check.ps1` | `.agents/skills/B01_框架体检/scripts/framework-check.ps1` |
| `normalize.ps1` | `.agents/skills/B06_项目规范化/scripts/normalize.ps1` |
| `remove.ps1` | `.agents/skills/B03_记忆管理/scripts/remove.ps1` |

> 完整根因分析、踩坑经过、操作规则详见知识提炼 [PowerShell 编码陷阱](../../.memory/知识提炼/PowerShell 编码陷阱.md)。本节约定操作规则（事实源），知识提炼承载完整上下文。
