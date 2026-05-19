# Changelog

All notable public changes to this project are documented here.

## [Unreleased]

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
