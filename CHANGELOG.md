# Changelog

All notable public changes to this project are documented here.

## [Unreleased]

## [v2.18.0] - 2026-10-03

### Highlights

- 新增 F02 拾序问题记录技能：整理用户问题、由 AI 定义开放分类、检查相似项，并通过 MCP 保存和回读核对。
- 初始化工具内置 33 个注册技能与 workspace-spec v1.29.0，按最新注册表全量刷新模板。

### Added

- F02 配套受限 MCP 客户端，支持健康、列表、详情、新增和编辑；写请求先落盘，保留请求编号与并发版本，写入后核对结果。
- 提供分类规则、调用流程、请求模板及 Claude 命令入口。

### Upgrade Notes

- F02 需要另行部署拾序服务及 MCP Python 依赖；初始化工具不包含拾序应用或数据库，也不会自动修改客户端连接配置。
- 分类由执行技能的 AI 判断，允许新建分类；不改变拾序应用内部功能。
- 初始化与升级隔离验证通过，继续保留私人配置、输入、记忆和业务成果。

### Assets

- init_workspace_v2.18.0.exe
- Platform: Windows
- Size: 11,945,720 bytes (11.39 MB)
- SHA256: F068B7F85454B4DE9F2F8DB9BEB479C9BB30B853029029F573A0DA6BA06F31C8

### Full Diff

- https://github.com/tenbj/init_workspace/compare/v2.17.0...v2.18.0


## [v2.17.0] - 2026-10-02

### Highlights

- H01 默认同时设计手机与桌面体验，增加响应式合同及真实浏览器验收。
- H02 首次通过 D04/G02 生成架构与 ER 两个独立 HTML 页面，每次系统更新同步核对与维护。
- 新增 D04 架构页面生成技能，初始化工具内置 32 个注册技能及 workspace-spec v1.28.0。

### Changed

- H02 合同增加本轮交付标识、页面与来源哈希、维护说明及独立证据；既有页面形式与路径可继续沿用。
- 初始化模板按最新注册表全量刷新，重新封装 Windows 初始化程序。

### Fixed

- 工作内容备份在最终目录改名遇到短暂文件占用时有限重试；持续失败保留未完成快照，不修改 live 版本。

### Upgrade Notes

- H02 旧项目增量补齐页面及本轮核对证据，不能将旧报告直接认定为当前验收。
- 初始化升级继续保留私人配置、输入、记忆和业务成果。初始化前建议备份；exe 仅作为 Release 附件分发。

### Assets

- init_workspace_v2.17.0.exe
- Platform: Windows
- Size: 11,938,213 bytes (11.39 MB)
- SHA256: 9E9167F1CE261AF802442199F2516A1B4994F77FD10008BB00196D15B019DB65

### Full Diff

- https://github.com/tenbj/init_workspace/compare/v2.16.0...v2.17.0


## [v2.16.0] - 2026-10-02

### Highlights

- 新增 I01 内网穿透技能，提供 FRP TCP 配置备份、端口检查、NSSM 重启与公网验证流程。
- 汇集上次正式发布以来的原型与系统交付、单画布 ER 图、Git 工作流和备份保护更新。
- 修正初始化目录与当前 SSOT 的差异，重新构建 Windows 初始化工具，内置 31 个注册技能和 workspace-spec v1.27.0。

### Added

- I01_内网穿透：配置计划、候选校验、同目录字节备份、并发修改检查和默认小于 15000 的公网端口约束。
- G02_单画布ER图生成：单画布鸡脚关系、在线连接键、字段显隐及浏览器几何验收。
- H01_原型设计、H02_原型系统交付和 B11_Git分支工作流纳入本次公开版本。
- 初始化程序隔离验证脚本 verify_release.py，覆盖新建、升级、私人数据保留和内嵌仓库保护。

### Changed

- 初始化程序版本升级为 2.16.0，SSOT 版本对齐到 1.27.0。
- B09 模板更新按 registeredSkills 全量刷新，未注册的本地目录不进入公开包。
- Claude 命令按注册表生成；Git 流程及提交描述统一使用核心标准。
- 删除旧架构技能及隐式框架体检入口的历史变更随本版发布；B01 仅人工显式调用。

### Fixed

- 新建工作区使用稳定 output/00_系统治理 和对话记录路径。
- 从 SSOT 补齐任务进度目录与索引，并复制 Git版本控制标准.md 等全部标准模板。
- 工作内容备份排除 Git 元数据并保护链接及失败中间态；遇到托管技能包含 Git 仓库时拒绝覆盖。

### Security

- 内网穿透技能使用公开占位示例，不分发真实机器路径、部署域名或认证参数。
- 私人配置、memory/history/input/temp 继续留在提交边界之外；exe 仅作为 Release 附件。
- 已完成真实凭据匹配、GitHub token / 私钥模式扫描、模板与附件内容校验。

### Upgrade Notes

- 升级前仍先备份受管入口、规则、技能和标准，保留私人配置及用户输入/成果。
- 已存在的旧版核心项目目录保留原位；新工作区采用稳定目录名，不自动迁移历史用户项目。

### Assets

- init_workspace_v2.16.0.exe
- Platform: Windows
- Size: 11,900,753 bytes (11.35 MB)
- SHA256: 9BBEE4E995FD3BAA0422E883DF71ED0D3AE377CB706A0A8694D343EE1A4CF618

### Full Diff

- https://github.com/tenbj/init_workspace/compare/v2.15.0...v2.16.0

## [v2.15.0] - 2026-05-19

### Highlights

- 发布稳定 live 路径模型：`output/` 子项目、三分类目录和 `.memory/对话记录` 不再把版本号写进当前路径，版本由 `版本记录.md`、历史快照、Git tag 和 Release 承载。
- 发布稳定 Skill 命名模型：`.agents/skills` 目录、`.claude/commands` 文件和 `SKILL.md` YAML `name` 使用稳定名称，版本号保留在 `agents/openai.yaml` 的 `display_name`。
- 重新同步初始化程序模板并封装 Windows 附件 `init_workspace_v2.15.0.exe`，内置 `workspace-spec.json` v1.22.0 和 29 个注册 Skill。

### Changed

- `SKELETON_VERSION` 升级为 `2.15.0`。
- `SSO_SPEC_VERSION` 对齐到 `workspace-spec.json` v1.22.0。
- `README.md` 改为稳定源码路径和 `v2.15.0` 英文 exe 附件名。
- `B01_框架体检`、`B06_项目规范化`、`B02_版本控制备份`、`B04_子项目管理`、`A01_创建技能`、`A02_安装技能` 等受管模板同步稳定命名口径。
- 初始化程序模板从当前 live 工作区全量刷新：`AGENTS.md`、`CLAUDE.md`、4 个 Rule 文件、227 个 Skill 文件和 4 个标准文件。

### Security

- `*.exe` 继续只作为 GitHub Release 附件发布，不作为普通 Git 文件提交。
- `.Claude.json`、`.claude/settings.local.json`、`.memory/`、`.history/`、`.temp/` 和 `input/` 仍保持在普通提交边界之外。
- 本次发布前执行 B01 体检、SHA256 复算和敏感信息扫描。

### Upgrade Notes

- 新建工作区会直接使用稳定 Skill 路径和稳定 output 路径模型。
- 升级已有工作区时，初始化程序仍会先备份受管入口、Rules、Skills、Standards 和 Claude 命令，再替换为内置模板。
- 已有工作区中的历史 output 目录不会被 exe 强制迁移；如需消除旧 `_v*` live 路径，应按当前工作区标准单独执行规范化治理。
- 下载 GitHub Release 附件 `init_workspace_v2.15.0.exe`，不要从 Git 树中寻找二进制文件。

### Assets

- `init_workspace_v2.15.0.exe`
- Platform: Windows
- Source: `output/00_系统治理/03_代码程序/dist/init_workspace_v2.15.0.exe`
- Size: `10.79 MB` (`11,318,720` bytes)
- SHA256: `0F26289B2F869049E0042BB30C86BF2C06D31D668F473527D5DDEEF2BA53F65B`
- Build manifest: `output/00_系统治理/03_代码程序/dist/.b09_build_manifest.json`
- Update manifest: `output/00_系统治理/03_代码程序/src/.b09_update_manifest.json`

### Full Diff

- `v2.14.0...v2.15.0`

## [v2.14.0] - 2026-05-18

### Highlights

- Added the `G01_HTML交互产物_v1.0.0` Skill for single-file HTML reports, diagrams, decision artifacts, data explorers, and lightweight interactive tools.
- Refreshed bundled initializer templates from the live workspace, now including 29 registered Skills and `workspace-spec.json` v1.20.0.
- Rebuilt and published the Windows Release asset as `init_workspace_v2.14.0.exe`, with manifest-tracked source templates, size, and SHA256.

### Added

- `G01_HTML交互产物_v1.0.0` provides a project-level entry for HTML artifacts while keeping the imported 16-mode HTML skill package in references.
- The bundled templates now include the G01 Skill, HTML mode index, localized references, assets, and Claude command wrapper.
- Added HTML documentation under `output/02_Skills管理体系_v1.22.0/02_课题研究_v1.7.0/`, including the G01 usage guide and the `init_workspace` project overview.

### Changed

- `SKELETON_VERSION` is now `2.14.0`.
- `SSO_SPEC_VERSION` is aligned to `workspace-spec.json` v1.20.0.
- `Skills管理标准.md` is aligned to v1.13.0 and adds the G-domain HTML artifact category.
- README version and build paths now point to the v2.14.0 initializer.
- The initializer bundle was regenerated from current live sources: `AGENTS.md`, `CLAUDE.md`, 4 rule files, 227 Skill files, and 4 standard files.
- B09 release manifests are included with the source tree so the template refresh and executable build can be audited after release.

### Security

- The executable remains a GitHub Release asset only; `*.exe` is ignored for normal Git commits.
- Private/runtime paths remain outside the release commit boundary: `.Claude.json`, `.claude/settings.local.json`, `.memory/`, `.history/`, `.temp/`, and `input/`.
- The release candidate was checked with B01 and a sensitive-pattern scan before publishing.

### Upgrade Notes

- Existing workspaces can upgrade in place. The initializer backs up managed entry files, rules, Skills, standards, and Claude command wrappers before replacing them with the bundled templates.
- G01 adds HTML artifact generation capability without changing the existing B/A/C/D/E/F Skill call patterns.
- Download `init_workspace_v2.14.0.exe` from GitHub Release assets. The binary is intentionally not stored in the Git tree.

### Assets

- `init_workspace_v2.14.0.exe`
- Platform: Windows
- Source: `output/00_系统治理_v1.25.0/03_代码程序_v2.14.0/dist/init_workspace_v2.14.0.exe`
- Size: `10.8 MB` (`11,321,112` bytes)
- SHA256: `78C4EF40BF4B67044C9D15BD0AEF47C1A21DC6CCC53650DF98B1169B5D5C898E`
- Build manifest: `output/00_系统治理_v1.25.0/03_代码程序_v2.14.0/dist/.b09_build_manifest.json`
- Update manifest: `output/00_系统治理_v1.25.0/03_代码程序_v2.14.0/src/.b09_update_manifest.json`

### Full Diff

- `v2.13.0...v2.14.0`

## [v2.13.0] - 2026-05-15

### Highlights

- Added the `E03_模型命名建议_v1.0.0` Skill for lightweight model and field naming recommendations.
- Refreshed bundled initializer templates from the live workspace, now including 28 registered Skills and `workspace-spec.json` v1.19.0.
- Rebuilt the Windows Release asset with the English filename `init_workspace_v2.13.0.exe`.

### Added

- `E03_模型命名建议_v1.0.0` copies a model design workbook and writes recommended field names without running the full E01 review workflow.
- The bundled templates now include the E03 Skill, its script, references, and Claude command wrapper.

### Changed

- `SKELETON_VERSION` is now `2.13.0`.
- `SSO_SPEC_VERSION` is aligned to `workspace-spec.json` v1.19.0.
- `Skills管理标准.md` is aligned to v1.12.0 and lists three E-domain model design Skills.
- README version and build paths now point to the v2.13.0 initializer.

### Upgrade Notes

- Existing workspaces can continue to upgrade in place; managed files are backed up before replacement.
- Download the executable from GitHub Release assets. The binary is not intended to be committed as a normal Git file.

### Assets

- `init_workspace_v2.13.0.exe`
- Size: `11.16 MB`
- SHA256: `C2CCF3186875896446B4802354B43C7489D6A179BE34E330803C9C31E7264CC5`

### Full Diff

- `v2.12.0...v2.13.0`

## [v2.12.0] - 2026-05-15

### Highlights

- Upgraded the initializer to `v2.12.0` and changed the Release asset name to English: `init_workspace_v2.12.0.exe`.
- Refreshed bundled templates from the current live workspace, including 27 registered Skills and `workspace-spec.json` v1.18.1.
- Fixed Windows builds when PyInstaller is installed but the `pyinstaller` command is not on PATH.

### Changed

- `SKELETON_VERSION` is now `2.12.0`.
- `SSO_SPEC_VERSION` is aligned to `workspace-spec.json` v1.18.1.
- The build script now produces `init_workspace_v{version}.exe` instead of the previous Chinese filename.
- Release cleanup now removes both old Chinese initializer names and the new English initializer names before rebuilding.

### Fixed

- `build.ps1` now invokes PyInstaller through `python -m PyInstaller`, avoiding PATH-dependent build failures.
- Several `output/` subprojects were normalized to include all three required classification folders before release.

### Upgrade Notes

- Existing workspaces can continue to upgrade in place; managed files are backed up before replacement.
- Download the executable from GitHub Release assets. The binary is not intended to be committed as a normal Git file.

### Assets

- `init_workspace_v2.12.0.exe`
- Size: `11.16 MB`
- SHA256: `B0A92FDA67633541E2D0F194A6F0CA614D84D072290BD71F98DC3DB054EA5DB8`

### Full Diff

- `v2.11.0...v2.12.0`

## [v2.11.0] - 2026-05-12

### Highlights

- Added run-event logging for the initializer: every run appends an initialization or upgrade record to `.history/.system/更新日志.md`.
- Refreshed the initializer templates from the current live workspace and rebuilt `初始化工作区_v2.11.0.exe`.
- Added B09 release manifests so template sync and executable builds are traceable.

### Added

- `detect_operation_type()` identifies whether the target directory is a fresh initialization or an existing workspace upgrade.
- `.history/.system/更新日志.md` now receives `init_workspace_run_<timestamp>` entries with tool version, operation type, template source, result, and backup statistics.
- B09 update/build manifests record template sync inputs, build asset metadata, size, and SHA256.

### Changed

- The initializer now confirms upgrades with wording specific to existing workspace content.
- Bundled templates were refreshed from the current `AGENTS.md`, `CLAUDE.md`, `.agents/rules`, `.agents/skills`, and `.system/standards`.
- `SSO_SPEC_VERSION` is aligned to `workspace-spec.json` v1.14.0.

### Fixed

- Kept `.memory` and `.history` behavior non-destructive: the initializer still only fills missing memory/history structure and backs up managed assets before replacement.
- Verified that B01 accepts `init_workspace_run_*` entries without confusing them with `.system` folder snapshots.

### Security

- `.Claude.json`, `.claude/settings.local.json`, `.history/`, `.memory/`, `input/`, `.temp/`, and `*.exe` remain excluded from normal Git commits.

### Upgrade Notes

- Upgrading an existing workspace still backs up managed entry files, rules, skills, standards, and Claude command wrappers before replacing them with bundled templates.
- Release users should download the executable from GitHub Release assets instead of expecting the binary in the Git tree.

### Assets

- `初始化工作区_v2.11.0.exe`
- Size: `10.63 MB`
- SHA256: `2C35139CF47F256D83A2AB4A4AE6D5B748D75109A0CC02B3881B21133E7C9E19`

### Full Diff

- `v2.7.0...v2.11.0`

## [v2.6.1] - 2026-05-10

### Highlights

- Added `AGENTS.md` as the Codex entry file.
- Kept `AGENTS.md` and `CLAUDE.md` as thin strong-gate entrypoints.
- Centralized concrete rules in `.system/standards/`, `.agents/rules/`, and Skill files.
- Updated Skill intent routing to use stable IDs such as `B04` and `C01`.
- Added dedicated entry backup folders: `.history/AGENTS/` and `.history/CLAUDE/`.
- Removed the hardcoded C01 data-assets clone URL; clone URL is now provided by `DATA_ASSETS_REPO_URL` or `--clone-url`.
- Removed hardcoded Doris connection values from C02/C04 scripts and templates; connection data is now read from environment variables.
- Rebuilt the Windows executable as `初始化工作区_v2.6.1.exe`.
