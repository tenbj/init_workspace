# Security Policy

## Sensitive Local Files

Do not commit local credentials or private runtime configuration.

The repository intentionally ignores:

- `.Claude.json`
- `.claude/settings.local.json`
- `input/`
- `.temp/`
- `.history/`
- `*.exe`

Before publishing, run a staged secret scan and confirm no token-like values are included.

## Reporting

If you find a leaked credential in a published commit or release asset, revoke the credential first, then remove the affected artifact or rewrite the repository history as needed.
