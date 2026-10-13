#!/usr/bin/env python3
"""Read-only, bounded heuristic scan of outgoing Git blobs and release assets.

Exit 0: scan completed without findings; 1: findings; 2: incomplete/error.
Output deliberately contains no matched values or source excerpts.
"""
from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import zipfile
import zlib

MAX_FILE = 16 * 1024 * 1024
MAX_TOTAL = 256 * 1024 * 1024
MAX_OBJECTS = 10000
MAX_LIST = 8 * 1024 * 1024
MAX_SECRET_FILE = 1024 * 1024
MAX_SECRET_VALUES = 256
MAX_ZIP_MEMBERS = 2000
MAX_ZIP_RATIO = 1000
MAX_ZIP_DEPTH = 3
PLACEHOLDER = re.compile(
    r"(?i)(?:example|placeholder|changeme|replace[_ -]?me|your[_ -]|dummy|sample|"
    r"synthetic|fixture|redacted|not[_ -]?real|test[_ -]|^x{3,}$|^\*+$|^<.*>$|"
    r"^\$\{|^\{\{|^process\.env|^os\.(?:getenv|environ)|^getenv\(|^env\()"
)
SENSITIVE_KEY = re.compile(r"(?i)(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|database[_-]?url|connection[_-]?string|dsn)")
ASSIGNMENT = re.compile(
    r'''(?im)["']?([\w.-]*(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key)[\w.-]*)["']?\s*[:=]\s*(?:"([^"\r\n]*)"|'([^'\r\n]*)'|([^\s"',;#}\]\r\n]+))'''
)
PATTERNS = (
    ("R001_PRIVATE_KEY", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----")),
    ("R002_PROVIDER_TOKEN", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|xox[baprs]-[A-Za-z0-9-]{20,}|sk-(?:live-|proj-)?[A-Za-z0-9_-]{24,}|AKIA[A-Z0-9]{16})\b")),
)
URI_PASSWORD = re.compile(r"[a-z][a-z0-9+.-]*://[^\s/:@]+:([^\s/@]+)@", re.I)


class ScanError(Exception):
    pass


def git(repo: str, args: list[str], limit: int = MAX_LIST) -> bytes:
    """Capture bounded stdout; never forward Git diagnostics or credentials."""
    try:
        proc = subprocess.Popen(
            ["git", "-C", repo, *args], stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_NO_REPLACE_OBJECTS": "1", "GIT_NO_LAZY_FETCH": "1"},
        )
    except (OSError, ValueError):
        raise ScanError("GIT_UNAVAILABLE") from None
    output = bytearray()
    oversized = []

    def collect():
        while True:
            chunk = proc.stdout.read(65536)
            if not chunk:
                break
            if len(output) + len(chunk) > limit:
                oversized.append(True)
                proc.kill()
                break
            output.extend(chunk)

    reader = threading.Thread(target=collect, daemon=True)
    reader.start()
    try:
        code = proc.wait(timeout=60)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        reader.join(timeout=5)
        raise ScanError("GIT_TIMEOUT") from None
    reader.join(timeout=5)
    if reader.is_alive():
        raise ScanError("GIT_READ_INCOMPLETE")
    proc.stdout.close()
    if oversized:
        raise ScanError("GIT_OUTPUT_LIMIT")
    if code:
        raise ScanError("GIT_COMMAND_FAILED")
    return bytes(output)


def plausible(value: str, minimum: int = 8) -> bool:
    value = value.strip()
    if len(value) < minimum or PLACEHOLDER.search(value):
        return False
    if value.lower() in {"password", "password123", "secret123", "abcdef123456", "null", "none", "undefined"}:
        return False
    if re.fullmatch(r"replace[-_]with[-_][a-z0-9_-]+", value):
        return False  # complete instructional placeholder, not a substring
    if re.fullmatch(r"\${1,2}[A-Z_][A-Z0-9_]*", value):
        return False  # shell/Compose environment reference, including $$ escape
    return True


def private_value(value: str) -> bool:
    """Explicit private input: exclude only whole, recognizable placeholders."""
    if not value:
        return False
    return not re.fullmatch(
        r"(?i)(?:<[^>]+>|\$\{[^}]+\}|\{\{.*\}\}|\$[A-Z_][A-Z0-9_]*|"
        r"your[_ -](?:token|password|secret|key)(?:[_ -]here)?|"
        r"replace[_ -]?me|change[_ -]?me|redacted|x{3,}|\*+)", value
    )


def load_secrets(paths: list[str]) -> list[str]:
    values = set()
    for item in paths:
        try:
            with open(item, "rb") as handle:
                raw = handle.read(MAX_SECRET_FILE + 1)
            if len(raw) > MAX_SECRET_FILE:
                raise ScanError("SECRET_INPUT_LIMIT")
            source = raw.decode("utf-8-sig")
            for line in source.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[7:].lstrip()
                key, sep, value = line.partition("=")
                if not sep or not SENSITIVE_KEY.search(key):
                    continue
                value = value.strip()
                if value[:1] in {"'", '"'}:
                    quote = value[0]
                    if len(value) < 2 or value[-1] != quote:
                        raise ScanError("SECRET_INPUT_FORMAT")
                    value = value[1:-1]
                else:
                    value = re.split(r"\s+#", value, maxsplit=1)[0].rstrip()
                if private_value(value):
                    if len(value) > 4096 or len(values) >= MAX_SECRET_VALUES and value not in values:
                        raise ScanError("SECRET_VALUE_LIMIT")
                    values.add(value)
        except (OSError, UnicodeError, ValueError):
            raise ScanError("SECRET_INPUT_UNREADABLE") from None
    return sorted(values)


def rules(data: bytes, secrets: list[str]) -> list[str]:
    text = data.decode("utf-16") if data.startswith((b"\xff\xfe", b"\xfe\xff")) else data.decode("utf-8", errors="replace")
    found = set()
    for rule, pattern in PATTERNS:
        if any(not PLACEHOLDER.search(m.group(0)) for m in pattern.finditer(text)):
            found.add(rule)
    for match in ASSIGNMENT.finditer(text):
        value = next((part for part in match.groups()[1:] if part is not None), "")
        if match.group(4) is not None and re.fullmatch(
            r"crypto\.randomBytes\(\d+\)(?:\.toString\()?", value
        ):
            continue  # unquoted runtime generation; quoted lookalikes remain literals
        if plausible(value, 12) and re.search(r"[A-Za-z]", value) and re.search(r"[0-9!@$%&*]", value):
            found.add("R003_CREDENTIAL_LITERAL")
    if any(plausible(match.group(1)) for match in URI_PASSWORD.finditer(text)):
        found.add("R004_URI_PASSWORD")
    if any(secret.encode(encoding) in data for secret in secrets for encoding in ("utf-8", "utf-16-le", "utf-16-be")):
        found.add("R005_PRIVATE_VALUE_MATCH")
    return sorted(found)


def section():
    return {"complete": True, "scanned_files": 0, "scanned_bytes": 0, "archive_members": 0, "findings": [], "errors": []}


def error(result, code):
    result["complete"] = False
    if code not in result["errors"]:
        result["errors"].append(code)


def inspect_bytes(result, data, path, object_sha, secrets):
    if len(data) > MAX_FILE or result["scanned_bytes"] + len(data) > MAX_TOTAL:
        raise ScanError("CONTENT_SIZE_LIMIT")
    result["scanned_files"] += 1
    result["scanned_bytes"] += len(data)
    for rule in rules(data, secrets):
        result["findings"].append({"path": path, "object_sha": object_sha, "rule": rule})


def scan_content(result, data, path, object_sha, secrets, depth=0):
    inspect_bytes(result, data, path, object_sha, secrets)
    stream = io.BytesIO(data)
    if not path.lower().endswith(".zip") and not zipfile.is_zipfile(stream):
        return
    if depth >= MAX_ZIP_DEPTH:
        raise ScanError("ZIP_DEPTH_LIMIT")
    try:
        with zipfile.ZipFile(stream) as archive:
            members = archive.infolist()
            result["archive_members"] += len(members)
            if result["archive_members"] > MAX_ZIP_MEMBERS:
                raise ScanError("ZIP_MEMBER_LIMIT")
            for member in members:
                if member.is_dir():
                    continue
                if member.flag_bits & 1:
                    raise ScanError("ZIP_ENCRYPTED_MEMBER")
                if member.file_size > MAX_FILE or member.file_size + result["scanned_bytes"] > MAX_TOTAL:
                    raise ScanError("ZIP_CONTENT_LIMIT")
                if member.file_size > max(1, member.compress_size) * MAX_ZIP_RATIO:
                    raise ScanError("ZIP_RATIO_LIMIT")
                with archive.open(member) as handle:
                    content = handle.read(MAX_FILE + 1)
                if len(content) != member.file_size:
                    raise ScanError("ZIP_READ_INCOMPLETE")
                scan_content(result, content, path + "/" + member.filename, object_sha, secrets, depth + 1)
    except (OSError, ValueError, RuntimeError, EOFError, zlib.error, zipfile.BadZipFile, NotImplementedError):
        raise ScanError("ZIP_READ_FAILED") from None


def scan_git(repo, base, head, secrets):
    result = section()
    try:
        # Resolve refs first, preventing options/revision expressions in rev-list.
        base_sha = git(repo, ["rev-parse", "--verify", "--end-of-options", base + "^{commit}"], 256).decode().strip()
        head_sha = git(repo, ["rev-parse", "--verify", "--end-of-options", head + "^{commit}"], 256).decode().strip()
        lines = git(repo, ["rev-list", "--objects", base_sha + ".." + head_sha]).splitlines()
        if len(lines) > MAX_OBJECTS:
            raise ScanError("OBJECT_COUNT_LIMIT")
        for line in lines:
            sha, _, path = line.partition(b" ")
            sha = sha.decode("ascii")
            kind = git(repo, ["cat-file", "-t", sha], 128).strip()
            if kind != b"blob":
                continue
            size = int(git(repo, ["cat-file", "-s", sha], 128))
            if size > MAX_FILE or result["scanned_bytes"] + size > MAX_TOTAL:
                raise ScanError("CONTENT_SIZE_LIMIT")
            data = git(repo, ["cat-file", "blob", sha], MAX_FILE)
            if len(data) != size:
                raise ScanError("OBJECT_READ_INCOMPLETE")
            scan_content(result, data, path.decode("utf-8", errors="replace"), sha, secrets)
    except (ScanError, ValueError, UnicodeError) as exc:
        error(result, str(exc) if isinstance(exc, ScanError) else "OBJECT_READ_FAILED")
    return result


def scan_assets(paths, secrets):
    result = section()
    for index, item in enumerate(paths):
        # Do not disclose caller's absolute/local path in output.
        label = "asset[" + str(index) + "]"
        try:
            with open(item, "rb") as handle:
                data = handle.read(MAX_FILE + 1)
            if Path(item).suffix.lower() == ".zip":
                label += ".zip"
            scan_content(result, data, label, None, secrets)
        except (OSError, ValueError, RuntimeError, UnicodeError, EOFError, zlib.error, zipfile.BadZipFile, NotImplementedError, ScanError) as exc:
            error(result, str(exc) if isinstance(exc, ScanError) else "ASSET_READ_FAILED")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-dir", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--secret-file", action="append", default=[])
    parser.add_argument("--asset", action="append", default=[])
    args = parser.parse_args(argv)
    try:
        secrets = load_secrets(args.secret_file)
    except ScanError as exc:
        print(json.dumps({"status": "incomplete", "errors": [str(exc)]}))
        return 2
    report = {
        "scope": "New objects reachable from head but not base; assets scanned separately.",
        "limitation": "Heuristic assistance, not proof that every secret was identified. Base history, external LFS/submodule content, obfuscated values and non-ZIP compressed contents are outside this scan. Git may give only one representative path for a shared blob.",
        "git": scan_git(args.repo_dir, args.base, args.head, secrets),
        "assets": scan_assets(args.asset, secrets),
    }
    incomplete = not report["git"]["complete"] or not report["assets"]["complete"]
    findings = bool(report["git"]["findings"] or report["assets"]["findings"])
    report["status"] = "incomplete" if incomplete else "findings" if findings else "clean"
    # Private values may even appear in malicious Git/ZIP filenames.
    def redact(value):
        if isinstance(value, str):
            for secret in secrets:
                value = value.replace(secret, "[REDACTED]")
            return value
        if isinstance(value, list):
            return [redact(item) for item in value]
        if isinstance(value, dict):
            return {key: redact(item) for key, item in value.items()}
        return value
    print(json.dumps(redact(report), ensure_ascii=True))
    return 2 if incomplete else 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
