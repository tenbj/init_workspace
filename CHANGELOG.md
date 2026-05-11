# Changelog

All notable public changes to this project are documented here.

## [Unreleased]

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
