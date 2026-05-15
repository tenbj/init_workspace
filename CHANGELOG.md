# Changelog

All notable public changes to this project are documented here.

## [Unreleased]

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
