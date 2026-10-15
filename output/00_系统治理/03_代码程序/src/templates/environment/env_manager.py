"""Local connection selection without printing credential values (stdlib only)."""
from __future__ import annotations

import argparse
import json
import locale
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
from urllib.parse import quote, quote_plus


class ConfigError(Exception):
    """An error containing only a fixed code and optional variable names."""


ID_PATTERN = re.compile(r"[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*\Z")
VARIABLE_PATTERN = re.compile(r"[A-Z][A-Z0-9_]*\Z")
WINDOWS_DEVICE_NAMES = frozenset({'con', 'prn', 'aux', 'nul'} |
    {prefix+str(n) for prefix in ('com', 'lpt') for n in range(1, 10)})
BASE_ENVIRONMENT = frozenset({
    "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP",
    "USERPROFILE", "APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "PROGRAMFILES",
    "PROGRAMFILES(X86)", "HOME", "LANG", "LC_ALL", "TZ", "PYTHONIOENCODING",
})


def assert_plain_path(path: Path) -> None:
    for item in (path, *path.parents):
        try:
            metadata = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(metadata.st_mode) or getattr(metadata, "st_file_attributes", 0) & 0x400:
            raise ConfigError("linked_path_refused")


def read_catalog(workspace: Path) -> list[dict]:
    return read_catalog_from_directory(workspace.absolute() / ".envs")


def read_catalog_from_directory(directory: Path) -> list[dict]:
    path = directory / "catalog.json"
    assert_plain_path(path)
    try:
        content = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        raise ConfigError("catalog_unavailable_or_invalid") from None
    return validate_catalog(content)


def validate_catalog(content: dict) -> list[dict]:
    if not isinstance(content, dict) or set(content) != {"schema_version", "connections"}:
        raise ConfigError("catalog_schema_invalid")
    if content["schema_version"] != 1 or not isinstance(content["connections"], list):
        raise ConfigError("catalog_schema_invalid")
    seen = set()
    for entry in content["connections"]:
        fields = {"id", "purpose", "environment", "permission", "file", "required_variables"}
        if not isinstance(entry, dict) or not fields <= set(entry) or set(entry) - fields - {"secret_files"}:
            raise ConfigError("catalog_entry_invalid")
        if any(not isinstance(entry[k], str) for k in fields - {"required_variables"}):
            raise ConfigError("catalog_entry_invalid")
        connection_id = entry["id"]
        if (not ID_PATTERN.fullmatch(connection_id) or connection_id in seen or
                connection_id.split('.')[0].lower() in WINDOWS_DEVICE_NAMES):
            raise ConfigError("connection_id_invalid_or_duplicate")
        seen.add(connection_id)
        if entry["file"] != connection_id + ".env":
            raise ConfigError("credential_filename_invalid")
        names = entry["required_variables"]
        secret_files = entry.get("secret_files", {})
        if not isinstance(secret_files, dict):
            raise ConfigError("secret_file_routes_invalid")
        if not isinstance(names, list) or (not names and not secret_files):
            raise ConfigError("variable_names_invalid")
        if any(not isinstance(n, str) or not VARIABLE_PATTERN.fullmatch(n) for n in names):
            raise ConfigError("variable_names_invalid")
        if len(names) != len(set(names)) or any(n in BASE_ENVIRONMENT for n in names):
            raise ConfigError("variable_names_invalid")
        for variable, relative in secret_files.items():
            if not isinstance(variable, str) or not VARIABLE_PATTERN.fullmatch(variable) or variable in BASE_ENVIRONMENT or variable in names:
                raise ConfigError("secret_file_route_name_invalid")
            if not isinstance(relative, str) or "\\" in relative:
                raise ConfigError("secret_file_route_path_invalid")
            parts = PurePosixPath(relative).parts
            if len(parts) != 3 or parts[:2] != ("keys", connection_id) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]*", parts[2]):
                raise ConfigError("secret_file_route_path_invalid")
            if relative != "/".join(parts) or ".." in parts:
                raise ConfigError("secret_file_route_path_invalid")
            if parts[2].endswith('.') or parts[2].split('.')[0].lower() in WINDOWS_DEVICE_NAMES:
                raise ConfigError("secret_file_route_path_invalid")
    return content["connections"]


def parse_values(text: str) -> dict[str, str]:
    values = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ConfigError("dotenv_syntax_invalid")
        name, value = line.split("=", 1)
        name, value = name.strip(), value.strip()
        if not VARIABLE_PATTERN.fullmatch(name) or name in values:
            raise ConfigError("dotenv_variable_invalid_or_duplicate")
        if value.startswith(("'", '"')):
            end = value.find(value[0], 1)
            if end < 0 or (value[end + 1:].strip() and not value[end + 1:].strip().startswith("#")):
                raise ConfigError("dotenv_quote_invalid")
            value = value[1:end]
        else:
            value = value.split("#", 1)[0].rstrip()
        if "\x00" in value:
            raise ConfigError("dotenv_value_invalid")
        values[name] = value
    return values


def route_connection(workspace: Path, connection_id: str, variables=None, secret_files=None) -> dict:
    """Read public metadata only; selectors must match exactly and never widen."""
    entries = read_catalog(workspace)
    entry = next((e for e in entries if e["id"] == connection_id), None)
    if entry is None:
        raise ConfigError("connection_not_registered")
    selected = variables is not None or secret_files is not None
    names = list(variables or []) if selected else entry["required_variables"]
    files = list(secret_files or []) if selected else list(entry.get("secret_files", {}))
    if len(names) != len(set(names)) or len(files) != len(set(files)):
        raise ConfigError("duplicate_route_selector")
    if set(names) - set(entry["required_variables"]) or set(files) - set(entry.get("secret_files", {})):
        raise ConfigError("route_selector_not_registered")
    root = workspace.absolute() / ".envs"
    result = {"id": connection_id, "variables": names, "secret_files": {}}
    if names:
        path = root / entry["file"]
        assert_plain_path(path)
        result["environment_file"] = str(path)
    for name in files:
        path = root / entry["secret_files"][name]
        assert_plain_path(path)
        result["secret_files"][name] = str(path)
    return result


def load_connection(workspace: Path, connection_id: str) -> dict[str, str]:
    route = route_connection(workspace, connection_id)
    required = set(route["variables"])
    values = {}
    if required:
        path = Path(route["environment_file"])
        assert_plain_path(path)
        try:
            values = parse_values(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError):
            raise ConfigError("credential_file_unavailable") from None
    if set(values) - required:
        raise ConfigError("unregistered_variables")
    missing = sorted(n for n in required if not values.get(n))
    if missing:
        raise ConfigError("missing_variables:" + ",".join(missing))
    for name, filename in route["secret_files"].items():
        if not Path(filename).is_file():
            raise ConfigError("secret_file_unavailable")
        values[name] = filename
    return values


def public_payload(workspace: Path) -> dict[str, bytes]:
    """Allowlist distributable content; actual .env files are never opened."""
    return public_payload_from_directory(workspace.absolute() / ".envs")


def public_payload_from_directory(root: Path) -> dict[str, bytes]:
    entries = read_catalog_from_directory(root)
    paths = [".gitignore", "README.md", "catalog.json", "env_manager.py"]
    for entry in entries:
        if not entry["required_variables"]:
            continue
        name = "examples/" + entry["file"] + ".example"
        path = root / name
        assert_plain_path(path)
        try:
            values = parse_values(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError):
            raise ConfigError("public_example_unavailable") from None
        if set(values) != set(entry["required_variables"]) or any(values.values()):
            raise ConfigError("public_example_must_be_blank")
        paths.append(name)
    payload = {}
    for name in paths:
        path = root / name
        assert_plain_path(path)
        try:
            payload[name] = path.read_bytes()
        except OSError:
            raise ConfigError("public_file_unavailable") from None
    return payload


def export_public(workspace: Path, destination: Path) -> int:
    payload = public_payload(workspace)
    source = workspace.absolute() / ".envs"
    destination = destination.absolute()
    assert_plain_path(destination)
    if destination == source or source in destination.parents:
        raise ConfigError("export_destination_invalid")
    if destination.exists():
        for path in destination.rglob("*"):
            assert_plain_path(path)
            if path.is_file() and path.relative_to(destination).as_posix() not in payload:
                raise ConfigError("export_destination_has_unmanaged_files")
    for name, contents in payload.items():
        path = destination / name
        assert_plain_path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)
    return len(payload)


def run_connection(workspace: Path, connection_id: str, command: list[str]) -> int:
    values = load_connection(workspace, connection_id)
    if command[:1] == ["--"]:
        command = command[1:]
    if not command:
        raise ConfigError("command_missing")
    if any(n in os.environ and os.environ[n] != v for n, v in values.items()):
        raise ConfigError("existing_environment_conflict")
    child_env = {k: v for k, v in os.environ.items() if k.upper() in BASE_ENVIRONMENT}
    child_env.update(values)
    try:
        result = subprocess.run(command, env=child_env, capture_output=True, shell=False)
    except OSError:
        raise ConfigError("command_could_not_start") from None
    # Replace bytes before decoding, including common URL encodings of values.
    markers = set()
    for value in values.values():
        for form in (value, quote(value, safe=""), quote_plus(value)):
            for encoding in {"utf-8", locale.getpreferredencoding(False), "gb18030"}:
                try:
                    markers.add(form.encode(encoding))
                except UnicodeEncodeError:
                    pass
    for payload, destination in ((result.stdout, sys.stdout), (result.stderr, sys.stderr)):
        for marker in sorted(markers, key=len, reverse=True):
            payload = payload.replace(marker, b"[REDACTED]")
        destination.write(payload.decode("utf-8", errors="replace"))
        destination.flush()
    return result.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Select local connections; never display credentials.")
    parser.add_argument("--workspace", type=Path, default=Path(__file__).absolute().parent.parent)
    actions = parser.add_subparsers(dest="action", required=True)
    actions.add_parser("list")
    route_parser = actions.add_parser("route")
    route_parser.add_argument("connection_id")
    route_parser.add_argument("--variable", action="append")
    route_parser.add_argument("--secret-file", action="append")
    export = actions.add_parser("export-public")
    export.add_argument("--destination", type=Path, required=True)
    for action in ("check", "run"):
        child = actions.add_parser(action)
        child.add_argument("connection_id")
        if action == "run":
            child.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    try:
        if args.action == "route":
            result = route_connection(args.workspace, args.connection_id, args.variable, args.secret_file)
            print(json.dumps(result, ensure_ascii=True))
            return 0
        if args.action == "export-public":
            count = export_public(args.workspace, args.destination)
            print(json.dumps({"public_files_exported": count}))
            return 0
        if args.action == "list":
            entries = read_catalog(args.workspace)
            result = []
            for entry in entries:
                path = args.workspace / ".envs" / entry["file"]
                assert_plain_path(path)
                result.append({"id": entry["id"], "environment": entry["environment"],
                               "permission": entry["permission"], "file_present": path.is_file()})
            print(json.dumps(result, ensure_ascii=True))
            return 0
        if args.action == "check":
            load_connection(args.workspace, args.connection_id)
            print(json.dumps({"configured": True, "remote_tested": False}))
            return 0
        return run_connection(args.workspace, args.connection_id, args.command)
    except ConfigError as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=True), file=sys.stderr)
        return 2
    except (OSError, ValueError):
        print('{"ok":false,"error":"local_operation_failed"}', file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
