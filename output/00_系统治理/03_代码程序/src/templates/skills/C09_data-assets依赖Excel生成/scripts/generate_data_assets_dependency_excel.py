#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

try:
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.table import Table, TableStyleInfo
    from openpyxl.utils import get_column_letter
except Exception as exc:  # pragma: no cover - CLI guard
    raise SystemExit(
        "缺少 Python 依赖 openpyxl，无法生成 xlsx。请先在当前 Python 环境安装 openpyxl。"
    ) from exc


DEFAULT_REPO_RELATIVE = "input/data-assets"
DEFAULT_CLONE_URL = ""
DEFAULT_OUTPUT_RELATIVE = ".temp/data-assets依赖清单.xlsx"
SCRIPT_EXTENSIONS = {".sql", ".py"}
IDENT = r'(?:[`"\[]?[A-Za-z_][\w$]*[`"\]]?|\{[^}]+\})'
LAYER_NAMES = {
    "ods",
    "dwd",
    "dws",
    "ads",
    "dim",
    "ref",
    "dma",
    "dmt",
    "dmd",
    "dwtmp",
    "etlods",
    "ext",
    "quality",
    "sys",
    "transmitter",
    "report",
    "ai",
    "application",
    "business",
    "data",
}


@dataclass
class Ref:
    db: str
    table: str
    raw: str
    source: str = ""

    @property
    def key(self) -> str:
        return f"{self.db}.{self.table}"


@dataclass
class FileRecord:
    id: str
    file_name: str
    path: str
    abs_path: Path
    ext: str
    is_primary: bool
    is_aux_partition: bool
    targets: list[Ref] = field(default_factory=list)
    is_data: bool = False
    table_names: list[str] = field(default_factory=list)


@dataclass
class TableRecord:
    key: str
    id: str
    name: str
    db: str
    files: list[FileRecord] = field(default_factory=list)
    aliases: set[str] = field(default_factory=set)
    target_sources: set[str] = field(default_factory=set)
    inferred: bool = False
    path_dirs: set[str] = field(default_factory=set)

    @property
    def full_name(self) -> str:
        return f"{self.db}.{self.name}"


@dataclass
class Edge:
    up: TableRecord
    down: TableRecord


@dataclass
class ParseResult:
    repo_root: Path
    commit: str
    branch: str
    tracked_count: int
    script_count: int
    file_records: list[FileRecord]
    tables: list[TableRecord]
    edges: list[Edge]
    up_counts: dict[str, int]
    down_counts: dict[str, int]
    external_refs: list[tuple[TableRecord, Ref, FileRecord]]
    ambiguous_refs: list[tuple[TableRecord, Ref, FileRecord, list[TableRecord]]]
    no_segment_match: list[tuple[TableRecord, FileRecord]]
    multi_file_dirs: dict[str, list[FileRecord]]


def run_command(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=str(cwd),
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode != 0:
        cmd = " ".join(args)
        raise RuntimeError(f"命令失败：{cmd}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    return result


def find_workspace_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".history").exists() and (candidate / ".memory").exists():
            return candidate
    raise RuntimeError("找不到工作区根目录：缺少 .history 或 .memory。")


def resolve_repo_path(workspace: Path, repo_arg: str | None, repo_relative: str) -> Path:
    if repo_arg:
        return Path(repo_arg).resolve()
    return (workspace / repo_relative).resolve()


def ensure_repo(repo: Path, remote: str, branch: str, clone_url: str) -> None:
    if not repo.exists() or (repo.is_dir() and not any(repo.iterdir())):
        if not clone_url or not clone_url.strip():
            raise ValueError("仓库缺失时必须显式提供 --clone-url；无默认企业仓库。")
        repo.parent.mkdir(parents=True, exist_ok=True)
        run_command(["git", "clone", "--origin", remote, "--branch", branch, clone_url, str(repo)], cwd=repo.parent)
        return
    if not (repo / ".git").exists():
        raise RuntimeError(f"目标目录存在但不是 Git 仓库：{repo}")


def sync_repo(repo: Path, remote: str, branch: str) -> None:
    run_command(["git", "remote", "set-url", "--push", remote, "DISABLED"], cwd=repo)
    run_command(["git", "fetch", remote, branch], cwd=repo)
    run_command(["git", "reset", "--hard"], cwd=repo)
    run_command(["git", "clean", "-fdx"], cwd=repo)
    run_command(["git", "checkout", "-B", branch, f"{remote}/{branch}"], cwd=repo)
    run_command(["git", "reset", "--hard", f"{remote}/{branch}"], cwd=repo)
    run_command(["git", "clean", "-fdx"], cwd=repo)


def git_files(repo: Path, include_untracked: bool) -> tuple[list[str], int]:
    if include_untracked:
        files: list[str] = []
        for path in repo.rglob("*"):
            if path.is_file() and ".git" not in path.parts and path.suffix.lower() in SCRIPT_EXTENSIONS:
                files.append(path.relative_to(repo).as_posix())
        return sorted(files), len(files)

    result = run_command(["git", "ls-files"], cwd=repo)
    all_files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    scripts = [path for path in all_files if Path(path).suffix.lower() in SCRIPT_EXTENSIONS]
    return scripts, len(all_files)


def git_commit(repo: Path) -> str:
    return run_command(["git", "log", "-1", "--oneline"], cwd=repo).stdout.strip()


def norm_ident(text: str | None) -> str:
    if not text:
        return ""
    value = str(text).strip()
    value = re.sub(r'^[`"\[]+|[`"\]]+$', "", value)
    value = re.sub(r";+$", "", value)
    return value.lower()


def clean_table_name(name: str) -> str:
    return re.sub(r"_cluster$", "", norm_ident(name))


def split_ref(raw: str | None) -> Ref | None:
    if not raw:
        return None
    value = str(raw).strip()
    if not value or value.startswith("(") or "{" in value or "}" in value:
        return None
    value = re.sub(r'^[`"\[]+|[`"\],;\)]+$', "", value)
    value = re.sub(r"\s+.*$", "", value)
    if not value or value.endswith("."):
        return None

    parts = [norm_ident(part) for part in value.split(".") if norm_ident(part)]
    if not parts:
        return None
    if len(parts) == 1:
        db = ""
        table = parts[0]
    else:
        db = ".".join(parts[:-1])
        table = parts[-1]
    table = clean_table_name(table)
    if not table or table in {"select", "where", "on", "as", "query", "values", "into", "table"}:
        return None
    if not db and re.match(r"^(ck|mysql|pg|doris|hive)?_?[a-z0-9]+_db$", table, re.I):
        return None
    return Ref(db=db, table=table, raw=value)


def strip_sql_comments(text: str) -> str:
    text = re.sub(r"/\*[\s\S]*?\*/", " ", text)
    return re.sub(r"--[^\r\n]*", " ", text)


def collect_assignments(text: str) -> dict[str, str]:
    assignments: dict[str, str] = {}
    for match in re.finditer(r"(?:self\.)?([A-Za-z_]\w*)\s*=\s*['\"]([A-Za-z0-9_]+)['\"]", text):
        assignments[match.group(1)] = match.group(2)
        assignments[f"self.{match.group(1)}"] = match.group(2)
    return assignments


def subst_vars(raw: str, assignments: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        expr = match.group(1).strip()
        if expr in assignments:
            return assignments[expr]
        last = expr.split(".")[-1]
        return assignments.get(last, "")

    return re.sub(r"\{([^}]+)\}", replace, raw)


def add_target(targets: list[Ref], raw: str, source: str, assignments: dict[str, str]) -> None:
    ref = split_ref(subst_vars(raw, assignments))
    if ref:
        ref.source = source
        targets.append(ref)


def each_regex(text: str, pattern: str) -> Iterable[re.Match[str]]:
    for match in re.finditer(pattern, text, flags=re.I):
        end = match.start() + len(match.group(0))
        if end < len(text) and text[end] == ".":
            continue
        yield match


def extract_targets(text: str, rel_path: str) -> list[Ref]:
    ext = Path(rel_path).suffix.lower()
    assignments = collect_assignments(text)
    sql_text = strip_sql_comments(text)
    targets: list[Ref] = []

    insert_pattern = rf"\binsert\s+(?:overwrite\s+)?(?:into\s+|table\s+)?(({IDENT})(?:\.({IDENT})){{0,2}})"
    create_pattern = rf"\bcreate\s+(?:or\s+replace\s+)?(?:table|view)\s+(?:if\s+not\s+exists\s+)?(({IDENT})(?:\.({IDENT})){{0,2}})"
    truncate_pattern = rf"\btruncate\s+(?:table\s+)?(({IDENT})(?:\.({IDENT})){{0,2}})"
    for match in each_regex(sql_text, insert_pattern):
        add_target(targets, match.group(1), "insert", assignments)
    for match in each_regex(sql_text, create_pattern):
        add_target(targets, match.group(1), "create", assignments)
    for match in each_regex(sql_text, truncate_pattern):
        add_target(targets, match.group(1), "truncate", assignments)

    if ext == ".py":
        for match in re.finditer(r"\.write\.jdbc\([\s\S]{0,700}?\btable\s*=\s*f?['\"]([^'\"]+)['\"]", text, re.I):
            add_target(targets, match.group(1), "write.jdbc", assignments)
        for match in re.finditer(r"\bto_mysql\s*\([^\)]*?,\s*['\"]([A-Za-z_]\w*)['\"]", text, re.I):
            add_target(targets, match.group(1), "to_mysql", assignments)
        for match in re.finditer(r"\bto_ck1\s*\([^\)]*?,\s*['\"]([A-Za-z_]\w*)['\"]", text, re.I):
            add_target(targets, match.group(1), "to_ck1", assignments)
        for match in re.finditer(r"\brename\s+table\s+[A-Za-z_]\w*\s+to\s+([A-Za-z_]\w*)", text, re.I):
            add_target(targets, match.group(1), "rename", assignments)

    seen: set[str] = set()
    result: list[Ref] = []
    for target in targets:
        key = f"{target.db}.{target.table}.{target.source}"
        if key not in seen:
            seen.add(key)
            result.append(target)
    return result


def extract_refs(text: str) -> list[Ref]:
    sql_text = strip_sql_comments(text)
    pattern = r'\b(?:from|join)\s+((?:[`"\[]?[A-Za-z_][\w$]*[`"\]]?)(?:\.(?:[`"\[]?[A-Za-z_][\w$]*[`"\]]?)){0,2})'
    refs: list[Ref] = []
    for match in re.finditer(pattern, sql_text, re.I):
        ref = split_ref(match.group(1))
        if ref:
            refs.append(ref)
    seen: set[str] = set()
    result: list[Ref] = []
    for ref in refs:
        if ref.key not in seen:
            seen.add(ref.key)
            result.append(ref)
    return result


def infer_db_from_path(rel_path: str, table: str) -> str:
    parts = rel_path.split("/")
    lower = [part.lower() for part in parts]
    first = parts[0] if parts else ""
    layer = next((item for item in lower if item in LAYER_NAMES), "")

    if first == "cbebg":
        return "cbebg"
    if first == "glcd":
        return "glcd"
    if first == "dpxbg":
        return "dpxbg"
    if first == "dpxbg-tgp":
        return "dpxbg_tgp"
    if first == "doris-test":
        return norm_ident(parts[1]) if len(parts) > 1 else "doris_test"
    if first == "cbebg-ck":
        return {
            "ods": "ck_ods_db",
            "etlods": "ck_ods_db",
            "dwd": "ck_dwd_db",
            "dws": "ck_dws_db",
            "ads": "ck_ads_db",
            "dim": "ck_dim_db",
        }.get(layer, "ck_bak_db")
    if first == "dw-data":
        return {
            "dim": "ck_dim_db",
            "dws": "ck_dws_db",
            "ods": "ck_ods_db",
            "etlods": "ck_ods_db",
            "dwd": "ck_dwd_db",
            "dmd": "ck_dmd_db",
            "ext": "ck_extra_db",
        }.get(layer, "ck_bak_db")
    if first == "dp-data":
        return "data_platform"
    if first == "dw-log":
        return "ck_bak_db"
    return norm_ident(first)


def target_rank(target: Ref) -> int:
    rank = 50
    if target.source in {"insert", "create"}:
        rank -= 20
    if target.source in {"write.jdbc", "to_mysql", "to_ck1"}:
        rank -= 10
    if target.source == "truncate":
        rank += 5
    if target.db == "ck_bak_db":
        rank += 20
    if re.search(r"(_temp|_bak)$", target.table):
        rank += 15
    return rank


def split_statements(text: str, ext: str) -> list[str]:
    if ext == ".py":
        parts = re.split(r"(?m)^\s*#\s*In\[[^\n]*\]:\s*$", text)
        return [part.strip() for part in parts if part.strip()]
    return [part.strip() for part in re.split(r";;|;\s*(?:\r?\n|$)", text) if part.strip()]


def table_strings(table: TableRecord) -> set[str]:
    values = {
        table.name,
        f"{table.name}_cluster",
        f"{table.db}.{table.name}",
        f"{table.db}.{table.name}_cluster",
    }
    for alias in table.aliases:
        values.add(alias)
        values.add(f"{alias}_cluster")
    return {value.lower() for value in values if value}


def segment_targets_match(segment: str, table: TableRecord) -> bool:
    lowered = segment.lower()
    for value in table_strings(table):
        escaped = re.escape(value)
        pattern = (
            r"\b(?:insert\s+(?:overwrite\s+)?(?:into\s+|table\s+)?|"
            r"truncate\s+(?:table\s+)?|"
            r"create\s+(?:or\s+replace\s+)?(?:table|view)\s+|"
            r"alter\s+table\s+|"
            r"table\s*=\s*f?['\"]?|"
            r"to_ck1\s*\([^\)]*?,\s*['\"]|"
            r"to_mysql\s*\([^\)]*?,\s*['\"])"
            + escaped
            + r"\b"
        )
        if re.search(pattern, lowered, re.I):
            return True
    return False


def parse_repository(repo_root: Path, scripts: list[str], tracked_count: int, branch: str) -> ParseResult:
    file_records: list[FileRecord] = []
    table_map: dict[str, TableRecord] = {}
    text_by_file: dict[str, str] = {}

    def ensure_table(db: str, table: str, file_record: FileRecord, target: Ref | None, inferred: bool) -> TableRecord | None:
        table = clean_table_name(table)
        db = norm_ident(db or infer_db_from_path(file_record.path, table))
        if not table:
            return None
        key = f"{db}.{table}"
        record = table_map.get(key)
        if not record:
            record = TableRecord(key=key, id="", name=table, db=db, inferred=inferred)
            table_map[key] = record
        record.files.append(file_record)
        record.path_dirs.add(str(Path(file_record.path).parent).replace("\\", "/"))
        record.aliases.add(f"{db}.{table}")
        record.aliases.add(f".{table}")
        if target:
            record.target_sources.add(target.source)
            if target.db:
                record.aliases.add(f"{target.db}.{target.table}")
        return record

    for index, rel_path in enumerate(scripts, start=1):
        abs_path = repo_root / Path(rel_path)
        try:
            text = abs_path.read_text(encoding="utf-8", errors="replace")
        except UnicodeDecodeError:
            text = abs_path.read_text(encoding="gbk", errors="replace")
        text_by_file[rel_path] = text

        stem = Path(rel_path).stem
        dir_leaf = Path(rel_path).parent.name
        ext = Path(rel_path).suffix.lower()
        targets = extract_targets(text, rel_path)
        is_primary = stem == dir_leaf
        is_aux_partition = stem.endswith("-partition") and stem[: -len("-partition")] == dir_leaf
        meaningful_targets = [target for target in targets if not target.table.endswith("_temp")]
        is_data = is_primary or any(not re.search(r"(_temp|_bak)$", target.table) for target in meaningful_targets)
        file_record = FileRecord(
            id=f"F{index:05d}",
            file_name=Path(rel_path).name,
            path=rel_path,
            abs_path=abs_path,
            ext=ext,
            is_primary=is_primary,
            is_aux_partition=is_aux_partition,
            targets=targets,
            is_data=is_data,
        )
        file_records.append(file_record)

        if not is_data:
            continue

        target_list = list(meaningful_targets)
        if not target_list and is_primary:
            target_list = [Ref(db=infer_db_from_path(rel_path, stem), table=stem, raw=stem, source="path-infer")]
        if is_primary and not any(target.table == clean_table_name(stem) for target in target_list):
            non_staging = [
                target
                for target in target_list
                if target.db and target.db != "ck_bak_db" and not target.table.endswith("_bak")
            ]
            if not non_staging:
                target_list.append(Ref(db=infer_db_from_path(rel_path, stem), table=stem, raw=stem, source="path-infer"))

        seen_targets: set[str] = set()
        for target in sorted(target_list, key=target_rank):
            db = target.db or infer_db_from_path(rel_path, target.table)
            table = clean_table_name(target.table)
            target_key = f"{db}.{table}"
            if target_key in seen_targets:
                continue
            seen_targets.add(target_key)
            table_record = ensure_table(db, table, file_record, target, target.source == "path-infer")
            if table_record and table_record.full_name not in file_record.table_names:
                file_record.table_names.append(table_record.full_name)

    tables = list(table_map.values())
    for key, record in list(table_map.items()):
        if record.db != "ck_bak_db":
            continue
        has_non_bak = any(
            table.name == record.name
            and table.db != "ck_bak_db"
            and bool(table.path_dirs & record.path_dirs)
            for table in tables
        )
        if has_non_bak and record.target_sources and all(source in {"truncate", "write.jdbc"} for source in record.target_sources):
            del table_map[key]

    tables = sorted(table_map.values(), key=lambda item: (item.name, item.db))
    for index, table in enumerate(tables, start=1):
        table.id = f"T{index:05d}"

    for file_record in file_records:
        file_record.table_names = []
    for table in tables:
        for file_record in table.files:
            if table.full_name not in file_record.table_names:
                file_record.table_names.append(table.full_name)
    for file_record in file_records:
        file_record.is_data = bool(file_record.table_names)

    exact_alias: dict[str, list[TableRecord]] = {}
    name_only: dict[str, list[TableRecord]] = {}
    for table in tables:
        aliases = set(table.aliases)
        aliases.add(table.full_name)
        aliases.add(f".{table.name}")
        for alias in aliases:
            if alias.startswith("."):
                continue
            exact_alias.setdefault(alias, []).append(table)
        name_only.setdefault(table.name, []).append(table)

    def resolve_ref(ref: Ref, context_db: str) -> tuple[str, TableRecord | None, list[TableRecord]]:
        candidates: list[TableRecord] = []
        if ref.db:
            candidates.extend(exact_alias.get(ref.key, []))
        else:
            candidates.extend(exact_alias.get(f"{context_db}.{ref.table}", []))
            if not candidates:
                candidates.extend(name_only.get(ref.table, []))
        unique = {candidate.id: candidate for candidate in candidates}
        values = list(unique.values())
        if len(values) == 1:
            return "resolved", values[0], values
        if len(values) > 1:
            return "ambiguous", None, values
        return "external", None, []

    edge_map: dict[str, Edge] = {}
    external_refs: list[tuple[TableRecord, Ref, FileRecord]] = []
    ambiguous_refs: list[tuple[TableRecord, Ref, FileRecord, list[TableRecord]]] = []
    no_segment_match: list[tuple[TableRecord, FileRecord]] = []

    for table in tables:
        for file_record in table.files:
            text = text_by_file.get(file_record.path, "")
            if len(file_record.table_names) <= 1:
                refs = extract_refs(text)
            else:
                refs = []
                for segment in split_statements(text, file_record.ext):
                    if segment_targets_match(segment, table):
                        refs.extend(extract_refs(segment))
                seen_refs: set[str] = set()
                refs = [ref for ref in refs if not (ref.key in seen_refs or seen_refs.add(ref.key))]
                if not refs:
                    no_segment_match.append((table, file_record))

            for ref in refs:
                if ref.table == table.name and (not ref.db or ref.db == table.db):
                    continue
                status, upstream, candidates = resolve_ref(ref, table.db)
                if status == "resolved" and upstream and upstream.id != table.id:
                    edge_map[f"{upstream.id}->{table.id}"] = Edge(up=upstream, down=table)
                elif status == "ambiguous":
                    ambiguous_refs.append((table, ref, file_record, candidates))
                else:
                    external_refs.append((table, ref, file_record))

    edges = sorted(edge_map.values(), key=lambda edge: (edge.down.id, edge.up.id))
    up_counts = {table.id: 0 for table in tables}
    down_counts = {table.id: 0 for table in tables}
    for edge in edges:
        up_counts[edge.down.id] += 1
        down_counts[edge.up.id] += 1

    multi_file_dirs: dict[str, list[FileRecord]] = {}
    for file_record in file_records:
        parent = str(Path(file_record.path).parent).replace("\\", "/")
        multi_file_dirs.setdefault(parent, []).append(file_record)

    return ParseResult(
        repo_root=repo_root,
        commit=git_commit(repo_root),
        branch=branch,
        tracked_count=tracked_count,
        script_count=len(scripts),
        file_records=file_records,
        tables=tables,
        edges=edges,
        up_counts=up_counts,
        down_counts=down_counts,
        external_refs=external_refs,
        ambiguous_refs=ambiguous_refs,
        no_segment_match=no_segment_match,
        multi_file_dirs=multi_file_dirs,
    )


def unique_join(values: Iterable[str]) -> str:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return ";".join(result)


def add_table_sheet(wb: Workbook, name: str, headers: list[str], rows: list[list[object]], widths: list[int]) -> None:
    ws = wb.create_sheet(title=name)
    ws.append(headers)
    for row in rows:
        ws.append(row)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    header_fill = PatternFill("solid", fgColor="164E63")
    header_font = Font(bold=True, color="FFFFFF")
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    for column_index, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(column_index)].width = width
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=False)
    if ws.max_row > 1 and ws.max_column > 0:
        table_name = f"DataTable{len(wb.worksheets):02d}"
        table = Table(displayName=table_name, ref=f"A1:{get_column_letter(ws.max_column)}{ws.max_row}")
        style = TableStyleInfo(name="TableStyleMedium2", showFirstColumn=False, showLastColumn=False, showRowStripes=True)
        table.tableStyleInfo = style
        ws.add_table(table)


def build_exception_rows(result: ParseResult) -> list[list[object]]:
    rows: list[list[object]] = []
    for file_record in result.file_records:
        if not file_record.is_data:
            rows.append(["非数据表文件", file_record.id, file_record.file_name, file_record.path, "脚本文件未识别到目标表，且文件名与所在最小目录不一致。"])
        if len(file_record.table_names) > 1:
            preview = ";".join(file_record.table_names[:20])
            suffix = "..." if len(file_record.table_names) > 20 else ""
            rows.append(["单文件多目标表", file_record.id, file_record.file_name, file_record.path, f"识别到 {len(file_record.table_names)} 个目标表：{preview}{suffix}"])

    for directory, files in result.multi_file_dirs.items():
        if len(files) > 1:
            rows.append(["单目录多脚本", unique_join(file.id for file in files), unique_join(file.file_name for file in files), directory, f"该最小目录含 {len(files)} 个 SQL/Python 脚本。"])

    for table, file_record in result.no_segment_match:
        rows.append(["多目标语句块未匹配", file_record.id, file_record.file_name, file_record.path, f"表 {table.id} {table.full_name} 在多目标文件中未匹配到独立语句块，依赖按空处理并保留异常。"])

    for table, ref, file_record, candidates in result.ambiguous_refs:
        rows.append(["依赖引用多候选", file_record.id, file_record.file_name, file_record.path, f"表 {table.id} 引用 {ref.key} 命中多个候选：{';'.join(item.id for item in candidates)}"])

    name_map: dict[str, list[TableRecord]] = {}
    for table in result.tables:
        name_map.setdefault(table.name, []).append(table)
    for name, tables in name_map.items():
        if len(tables) > 1:
            rows.append([
                "同名表多库/多路径",
                unique_join(file.id for table in tables for file in table.files),
                unique_join(file.file_name for table in tables for file in table.files),
                unique_join(file.path for table in tables for file in table.files),
                f"表名 {name} 对应 {len(tables)} 个表对象：{';'.join(table.full_name for table in tables)}",
            ])
    return rows


def write_workbook(result: ParseResult, output: Path) -> dict[str, int]:
    wb = Workbook()
    wb.remove(wb.active)

    file_rows = [
        [file.id, file.file_name, file.path, "是" if file.is_data else "否", ";".join(file.table_names)]
        for file in result.file_records
    ]
    table_rows = [
        [
            table.id,
            table.name,
            unique_join(file.file_name for file in table.files),
            unique_join(file.id for file in table.files),
            result.up_counts.get(table.id, 0),
            result.down_counts.get(table.id, 0),
        ]
        for table in result.tables
    ]
    downstream_rows = [
        [edge.up.name, edge.up.db, edge.up.id, edge.down.name, edge.down.db, edge.down.id]
        for edge in result.edges
    ]
    upstream_rows = [
        [edge.down.name, edge.down.db, edge.down.id, edge.up.name, edge.up.db, edge.up.id]
        for edge in result.edges
    ]
    external_rows = [
        [table.name, table.db, table.id, ref.table, ref.db, file.id, file.path]
        for table, ref, file in result.external_refs
    ]
    exception_rows = build_exception_rows(result)
    multi_target_count = sum(1 for file in result.file_records if len(file.table_names) > 1)
    multi_script_dirs = sum(1 for files in result.multi_file_dirs.values() if len(files) > 1)

    summary_rows = [
        ["仓库路径", str(result.repo_root)],
        ["同步分支", result.branch],
        ["同步提交", result.commit],
        ["盘点范围", "git ls-files tracked SQL/Python" if result.tracked_count else "文件系统 SQL/Python"],
        ["tracked 文件数", result.tracked_count],
        ["SQL/Python 脚本数", result.script_count],
        ["识别为数据表的脚本数", sum(1 for file in result.file_records if file.is_data)],
        ["未识别为数据表的脚本数", sum(1 for file in result.file_records if not file.is_data)],
        ["识别数据表数", len(result.tables)],
        ["repo 内直接依赖边数", len(result.edges)],
        ["外部上游引用数", len(result.external_refs)],
        ["单目录多脚本目录数", multi_script_dirs],
        ["单文件多目标表文件数", multi_target_count],
        ["依赖引用多候选数", len(result.ambiguous_refs)],
        ["多目标语句块未匹配数", len(result.no_segment_match)],
    ]

    add_table_sheet(wb, "文件清单", ["文件id", "文件名", "文件路径", "是否数据表", "数据表名"], file_rows, [12, 36, 90, 12, 90])
    add_table_sheet(wb, "数据表清单", ["数据表id", "数据表名", "文件名", "文件id", "上游依赖表数", "下游依赖表数"], table_rows, [12, 45, 45, 28, 16, 16])
    add_table_sheet(wb, "下游依赖明细", ["数据表名", "数据表库名", "数据表id", "下游表名", "下游表库名", "下游数据表id"], downstream_rows, [45, 20, 12, 45, 20, 16])
    add_table_sheet(wb, "上游依赖明细", ["数据表名", "数据表库名", "数据表id", "上游表名", "上游表库名", "上游数据表id"], upstream_rows, [45, 20, 12, 45, 20, 16])
    add_table_sheet(wb, "汇总", ["项目", "值"], summary_rows, [32, 100])
    add_table_sheet(wb, "外部上游引用", ["数据表名", "数据表库名", "数据表id", "外部上游表名", "外部上游库名", "文件id", "文件路径"], external_rows, [45, 20, 12, 45, 28, 12, 90])
    add_table_sheet(wb, "异常清单", ["异常类型", "文件id", "文件名", "文件路径", "说明"], exception_rows, [22, 24, 42, 90, 120])
    add_table_sheet(
        wb,
        "解析说明",
        ["项目", "说明"],
        [
            ["文件范围", "默认使用同步到 origin/master 后的 git ls-files；仅纳入 tracked 的 .sql/.py 文件。"],
            ["是否数据表", "优先按文件名 stem 等于所在最小目录名识别；若脚本显式写入/创建/truncate 表，也纳入识别。"],
            ["数据表名", "优先使用脚本中 insert/create/write/truncate/write.jdbc/to_mysql/to_ck1 目标；_cluster 后缀按逻辑表归一。"],
            ["依赖边", "从 from/join 直接引用解析；只统计能解析到本 Excel 数据表清单的数据表作为 repo 内依赖。"],
            ["外部上游", "无法解析到数据表清单的 from/join 引用放入外部上游引用，不计入数据表清单上下游数量。"],
            ["静态限制", "不执行 SQL/Python，不解析运行时复杂拼接、调度配置和跨系统元数据。"],
        ],
        [30, 120],
    )

    ws = wb["汇总"]
    top_down = sorted(result.tables, key=lambda table: result.down_counts.get(table.id, 0), reverse=True)[:30]
    top_up = sorted(result.tables, key=lambda table: result.up_counts.get(table.id, 0), reverse=True)[:30]
    ws["D1"] = "排名"
    ws["E1"] = "数据表id"
    ws["F1"] = "数据表库名"
    ws["G1"] = "数据表名"
    ws["H1"] = "下游依赖表数"
    ws["I1"] = "上游依赖表数"
    ws["K1"] = "排名"
    ws["L1"] = "数据表id"
    ws["M1"] = "数据表库名"
    ws["N1"] = "数据表名"
    ws["O1"] = "上游依赖表数"
    ws["P1"] = "下游依赖表数"
    for column in range(4, 17):
        ws.cell(1, column).font = Font(bold=True, color="FFFFFF")
        ws.cell(1, column).fill = PatternFill("solid", fgColor="0F766E" if column < 10 else "7C2D12")
    for row_index, table in enumerate(top_down, start=2):
        ws.append([]) if row_index > ws.max_row else None
        values = [row_index - 1, table.id, table.db, table.name, result.down_counts.get(table.id, 0), result.up_counts.get(table.id, 0)]
        for offset, value in enumerate(values, start=4):
            ws.cell(row_index, offset, value)
    for row_index, table in enumerate(top_up, start=2):
        values = [row_index - 1, table.id, table.db, table.name, result.up_counts.get(table.id, 0), result.down_counts.get(table.id, 0)]
        for offset, value in enumerate(values, start=11):
            ws.cell(row_index, offset, value)
    for column in ["D", "E", "F", "H", "I", "K", "L", "M", "O", "P"]:
        ws.column_dimensions[column].width = 18
    ws.column_dimensions["G"].width = 45
    ws.column_dimensions["N"].width = 45

    output.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output)
    loaded = load_workbook(output, read_only=True, data_only=False)
    required = {"文件清单", "数据表清单", "下游依赖明细", "上游依赖明细"}
    missing = required - set(loaded.sheetnames)
    if missing:
        raise RuntimeError(f"导出的 Excel 缺少必需 sheet：{', '.join(sorted(missing))}")
    return {
        "file_rows": len(file_rows),
        "table_rows": len(table_rows),
        "downstream_rows": len(downstream_rows),
        "upstream_rows": len(upstream_rows),
        "external_rows": len(external_rows),
        "exception_rows": len(exception_rows),
    }


def build_summary(result: ParseResult, output: Path, row_counts: dict[str, int]) -> dict[str, object]:
    return {
        "repo": str(result.repo_root),
        "branch": result.branch,
        "commit": result.commit,
        "output": str(output),
        "tracked_files": result.tracked_count,
        "script_files": result.script_count,
        "data_files": sum(1 for file in result.file_records if file.is_data),
        "non_data_files": sum(1 for file in result.file_records if not file.is_data),
        "tables": len(result.tables),
        "repo_dependency_edges": len(result.edges),
        "external_refs": len(result.external_refs),
        "ambiguous_refs": len(result.ambiguous_refs),
        "no_segment_match": len(result.no_segment_match),
        "row_counts": row_counts,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="同步并解析 data-assets 仓库，生成表上下游依赖 Excel。")
    parser.add_argument("--repo-relative", default=DEFAULT_REPO_RELATIVE, help="工作区内 data-assets 仓库相对路径")
    parser.add_argument("--repo", help="直接指定 data-assets 仓库路径")
    parser.add_argument("--output", help="输出 Excel 路径；默认写入 .temp")
    parser.add_argument("--branch", default="master", help="远端分支，默认 master")
    parser.add_argument("--remote", default="origin", help="远端名，默认 origin")
    parser.add_argument("--clone-url", default=DEFAULT_CLONE_URL, help="仓库缺失或为空目录时的 clone URL")
    sync = parser.add_mutually_exclusive_group()
    sync.add_argument("--no-sync", dest="no_sync", action="store_true", help="只扫描当前仓库（默认）")
    sync.add_argument("--force-sync", dest="no_sync", action="store_false", help="仅明确授权丢弃本地改动时使用；会 reset/clean")
    parser.set_defaults(no_sync=True)
    parser.add_argument("--include-untracked", action="store_true", help="扫描文件系统中的 .sql/.py，不局限于 git ls-files")
    parser.add_argument("--json-summary", help="将统计摘要另存为 JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace = find_workspace_root(Path.cwd())
    repo = resolve_repo_path(workspace, args.repo, args.repo_relative)
    output = Path(args.output).resolve() if args.output else (workspace / DEFAULT_OUTPUT_RELATIVE).resolve()

    if args.no_sync:
        if not (repo / ".git").exists():
            raise RuntimeError(f"只读扫描需要已有 Git 仓库，请先按授权准备：{repo}")
    else:
        ensure_repo(repo, args.remote, args.branch, args.clone_url)
        sync_repo(repo, args.remote, args.branch)

    scripts, tracked_count = git_files(repo, include_untracked=args.include_untracked)
    result = parse_repository(repo, scripts, tracked_count, args.branch)
    row_counts = write_workbook(result, output)
    summary = build_summary(result, output, row_counts)
    if args.json_summary:
        summary_path = Path(args.json_summary).resolve()
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
