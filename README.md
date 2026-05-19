# init_workspace

`init_workspace` 是一个用于初始化和升级知识型工作区骨架的本地工具。它把工作区的入口规则、Skill、标准、记忆目录、历史目录和输入/输出目录组织成一套可重复生成的结构。

## 它解决什么问题

- 新建工作区时，一次性生成标准目录、入口文件和基础规则。
- 升级旧工作区时，先备份受管文件，再覆盖为当前骨架模板。
- 同时支持 Codex 与 Claude Code 的入口文件：`AGENTS.md` 和 `CLAUDE.md`。
- 通过 `.system/standards/` 管理 SSOT 标准，避免规则散落在各个 Skill 中。
- 通过稳定 Skill 编号（如 `B04`、`C01`）做意图分流，降低 Skill 改名或版本升级后的维护成本。
- 每次运行初始化程序时，会在 `.history/.system/更新日志.md` 追加一条记录，标明本次是初始化还是升级。

## 当前版本

- 工作区骨架标准：`workspace-spec.json` v1.22.0
- 系统治理子项目：`00_系统治理`
- 初始化程序：v2.15.0
- Windows 可执行文件：`init_workspace_v2.15.0.exe`

GitHub Release 附件提供 `init_workspace_v2.15.0.exe`。本次附件大小为 `10.79 MB`（`11,318,720` bytes），SHA256 为 `0F26289B2F869049E0042BB30C86BF2C06D31D668F473527D5DDEEF2BA53F65B`；源码中保留构建脚本和 B09 manifest，可自行重新构建并校验。

## 快速使用

1. 下载 Release 中的 `init_workspace_v2.15.0.exe`。
2. 将 exe 放到目标工作区目录。
3. 双击运行，选择初始化或升级。
4. 工具会生成或更新 `.agents/`、`.system/`、`.memory/`、`.history/`、`input/`、`output/` 等目录。

升级已有工作区时，受管入口、规则、Skill 和标准会先进入 `.history/` 对应目录，再被当前模板覆盖。

## 从源码构建

在 Windows PowerShell 中运行：

```powershell
powershell -ExecutionPolicy Bypass -File "output\00_系统治理\03_代码程序\src\build.ps1"
```

构建结果会生成在：

```text
output/00_系统治理/03_代码程序/dist/
```

## 目录说明

```text
.agents/              Skill 与本地执行规则
.claude/commands/     Claude Code 斜杠命令
.system/standards/    工作区 SSOT 标准
.memory/              对话记录、知识提炼和系统记录
.history/             本机历史备份目录，Git 中只保留目录占位
input/                输入资料目录，Git 中只保留目录占位
output/               治理文档、研究产物和初始化程序源码
AGENTS.md             Codex 入口强制门
CLAUDE.md             Claude 入口强制门
```

## 发布与隐私

本仓库不会提交以下本机内容：

- `.Claude.json`
- `.claude/settings.local.json`
- `input/` 内的资料
- `.temp/` 内的临时文件
- `.history/` 内的历史快照
- `*.exe` 构建产物

这些文件可能包含本机配置、临时数据、历史快照或二进制产物。发布 exe 时请使用 GitHub Release 附件。

GitHub 授权、创建仓库和发布 Release 的完整流程见：

```text
docs/GitHub发布授权与Release流程.md
```

## 重要规则

- `AGENTS.md` 和 `CLAUDE.md` 只做入口强制门，不承载完整制度。
- 具体制度以 `.system/standards/`、`.agents/rules/` 和对应 Skill 为准。
- 跨 Skill 意图引用使用稳定编号，例如 `B04`，不要在意图文本里写完整 Skill 文件夹名。
- 私有配置只补缺，不覆盖，不提交。
- C01 同步仓库的 clone 地址通过 `DATA_ASSETS_REPO_URL` 或 `--clone-url` 提供，不写死在公开源码中。
