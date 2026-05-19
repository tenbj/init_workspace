from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET


NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}

FIELD_HEADERS = {
    "field_category": "字段分类",
    "field_subcategory": "二级分类",
    "field_order": "字段序号",
    "field_name": "字段名",
    "data_type": "字段数据类型",
    "field_desc": "字段描述",
    "reference_field": "参考字段",
    "reference_table": "参考库表",
    "is_retained": "是否保留",
    "is_deleted": "是否删除",
    "is_enum_field": "是否为枚举字段",
    "is_primary_key": "是否主键字段",
    "is_business_key": "是否业务主键",
    "remark": "备注",
}

DECISIONS = {
    "keep",
    "fill_safe",
    "suggest_with_review",
    "replace_suggestion",
    "need_human_confirm",
    "cannot_decide",
}

CONFIDENCES = {"high", "medium", "low"}
MODEL_PROJECT_TOPIC = "模型设计标准化"


def project_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / ".agents").exists() and (parent / "output").exists():
            return parent
    return Path.cwd()


def to_project_path(path: Path | str) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    return project_root() / p


def rel(path: Path | str) -> str:
    p = Path(path).resolve()
    root = project_root().resolve()
    try:
        return str(p.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(p)


def ensure_dir(path: Path | str) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def write_json(path: Path | str, data: Any) -> None:
    p = Path(path)
    ensure_dir(p.parent)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path | str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_jsonl(path: Path | str, rows: list[dict[str, Any]]) -> None:
    p = Path(path)
    ensure_dir(p.parent)
    with p.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path | str) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    rows: list[dict[str, Any]] = []
    with p.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{p}:{line_no} is not valid JSON: {exc}") from exc
    return rows


def write_csv(path: Path | str, rows: list[dict[str, Any]], headers: list[str]) -> None:
    p = Path(path)
    ensure_dir(p.parent)
    with p.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def sha256_file(path: Path | str) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def file_manifest(path: Path | str, role: str) -> dict[str, Any]:
    p = to_project_path(path)
    return {
        "role": role,
        "path": rel(p),
        "exists": p.exists(),
        "size_bytes": p.stat().st_size if p.exists() else None,
        "sha256": sha256_file(p) if p.exists() else None,
    }


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    return text.strip()


def normalize_header(value: Any) -> str:
    return re.sub(r"\s+", "", clean_text(value))


def col_to_index(col: str) -> int:
    n = 0
    for c in col:
        n = n * 26 + ord(c.upper()) - 64
    return n


def index_to_col(index: int) -> str:
    result = ""
    while index:
        index, rem = divmod(index - 1, 26)
        result = chr(65 + rem) + result
    return result


def cell_ref_to_index(ref_value: str) -> tuple[int, int]:
    m = re.match(r"([A-Z]+)(\d+)", ref_value)
    if not m:
        return 1, 1
    return int(m.group(2)), col_to_index(m.group(1))


def cell_ref(row_number: int, col_index: int) -> str:
    return f"{index_to_col(col_index)}{row_number}"


def cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    typ = cell.attrib.get("t")
    if typ == "s":
        v = cell.find("a:v", NS)
        if v is not None and v.text is not None:
            idx = int(v.text)
            return shared_strings[idx] if idx < len(shared_strings) else ""
        return ""
    if typ == "inlineStr":
        return "".join(t.text or "" for t in cell.iter(f"{{{NS['a']}}}t"))

    v = cell.find("a:v", NS)
    if v is not None and v.text is not None:
        return v.text

    f = cell.find("a:f", NS)
    if f is not None and f.text:
        return "=" + f.text
    return ""


def load_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    strings: list[str] = []
    for si in root.findall("a:si", NS):
        strings.append("".join(t.text or "" for t in si.iter(f"{{{NS['a']}}}t")))
    return strings


def resolve_sheet_path(target: str) -> str:
    target = target.lstrip("/")
    if target.startswith("xl/"):
        return target
    return "xl/" + target


def detect_sheet_type(sheet_name: str, rows: list[dict[str, Any]], workbook_role: str) -> str:
    if workbook_role == "standard_library":
        if "规则标准库" in sheet_name:
            return "standard_rules"
        if "映射标准库" in sheet_name:
            return "standard_mapping"
        return "standard_other"

    if "模型设计目录" in sheet_name:
        return "model_catalog"
    if "依赖" in sheet_name or "数据流" in sheet_name:
        return "dependency"
    if "内容概览" in sheet_name:
        return "overview"
    if "评审" in sheet_name:
        return "review"
    if "模板" in sheet_name:
        return "entity_template"
    if sheet_name.startswith("附."):
        return "appendix"
    if find_header_row(rows, ["字段名", "字段描述"]):
        return "entity_design"
    return "other"


def load_xlsx_xml(path: Path | str, workbook_role: str) -> dict[str, Any]:
    p = to_project_path(path)
    with zipfile.ZipFile(p) as zf:
        shared_strings = load_shared_strings(zf)
        workbook = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        rid_to_target = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in rels.findall("rel:Relationship", NS)
        }

        sheets: list[dict[str, Any]] = []
        for sheet_id, sheet_node in enumerate(workbook.find("a:sheets", NS), 1):
            sheet_name = sheet_node.attrib["name"]
            state = sheet_node.attrib.get("state", "visible")
            rid = sheet_node.attrib.get(f"{{{NS['r']}}}id")
            sheet_path = resolve_sheet_path(rid_to_target[rid])
            sheet_xml = ET.fromstring(zf.read(sheet_path))
            rows: list[dict[str, Any]] = []
            max_col_seen = 0
            max_row_seen = 0

            for row_node in sheet_xml.findall(".//a:sheetData/a:row", NS):
                row_number = int(row_node.attrib.get("r", len(rows) + 1))
                cells: dict[str, str] = {}
                for c in row_node.findall("a:c", NS):
                    ref_value = c.attrib.get("r", f"A{row_number}")
                    _, col_index = cell_ref_to_index(ref_value)
                    value = clean_text(cell_value(c, shared_strings))
                    if value != "":
                        cells[str(col_index)] = value
                        max_col_seen = max(max_col_seen, col_index)
                        max_row_seen = max(max_row_seen, row_number)
                if cells:
                    rows.append({"row_number": row_number, "cells": cells})

            sheet = {
                "sheet_id": sheet_id,
                "sheet_name": sheet_name,
                "state": state,
                "visible": state == "visible",
                "non_empty_rows": len(rows),
                "max_row_seen": max_row_seen,
                "max_col_seen": max_col_seen,
                "rows": rows,
            }
            sheet["detected_type"] = detect_sheet_type(sheet_name, rows, workbook_role)
            sheets.append(sheet)

    return {
        "file_path": rel(p),
        "file_hash": sha256_file(p),
        "sheet_count": len(sheets),
        "sheets": sheets,
    }


def row_values(row: dict[str, Any], max_col: int | None = None) -> list[str]:
    cells = row.get("cells", {})
    if max_col is None:
        max_col = max((int(c) for c in cells), default=0)
    return [cells.get(str(i), "") for i in range(1, max_col + 1)]


def row_contains(row: dict[str, Any], required_headers: list[str]) -> bool:
    values = {normalize_header(v) for v in row.get("cells", {}).values()}
    return all(normalize_header(h) in values for h in required_headers)


def find_header_row(rows: list[dict[str, Any]], required_headers: list[str]) -> dict[str, Any] | None:
    for row in rows:
        if row_contains(row, required_headers):
            return row
    return None


def header_map(header_row: dict[str, Any]) -> dict[str, int]:
    result: dict[str, int] = {}
    for col, value in header_row.get("cells", {}).items():
        text = normalize_header(value)
        if text:
            result[text] = int(col)
    return result


def get_by_header(row: dict[str, Any], header_to_col: dict[str, int], header_name: str) -> str:
    col = header_to_col.get(normalize_header(header_name))
    if not col:
        return ""
    return clean_text(row.get("cells", {}).get(str(col), ""))


def source_cell(header_to_col: dict[str, int], header_name: str, row_number: int) -> str:
    col = header_to_col.get(normalize_header(header_name))
    return cell_ref(row_number, col) if col else ""


def rows_to_records(rows: list[dict[str, Any]], required_header: str = "序号") -> list[dict[str, Any]]:
    header = find_header_row(rows, [required_header])
    if not header:
        return []
    hmap = header_map(header)
    records: list[dict[str, Any]] = []
    for row in rows:
        if row["row_number"] <= header["row_number"]:
            continue
        record = {
            name: clean_text(row.get("cells", {}).get(str(col), ""))
            for name, col in sorted(hmap.items(), key=lambda item: item[1])
        }
        if any(record.values()):
            record["_row_number"] = row["row_number"]
            records.append(record)
    return records


def declared_table_from_first_row(sheet: dict[str, Any]) -> str:
    rows = sheet.get("rows", [])
    if not rows:
        return ""
    first_text = clean_text(rows[0].get("cells", {}).get("1", ""))
    if not first_text:
        return ""
    table = re.split(r"[，,]", first_text, maxsplit=1)[0].strip()
    return table


def subproject_version_key(path: Path) -> tuple[int, int, int, str]:
    match = re.search(r"_v(\d+)\.(\d+)\.(\d+)$", path.name)
    if not match:
        return (-1, -1, -1, path.name)
    major, minor, patch = (int(part) for part in match.groups())
    return (major, minor, patch, path.name)


def latest_model_project() -> Path | None:
    root = project_root() / "output"
    stable_candidates = [
        path
        for path in root.iterdir()
        if path.is_dir() and re.match(rf"^\d+_{re.escape(MODEL_PROJECT_TOPIC)}$", path.name)
    ]
    if stable_candidates:
        return sorted(stable_candidates)[-1]

    legacy_candidates = [path for path in root.glob(f"*_{MODEL_PROJECT_TOPIC}_v*") if path.is_dir()]
    return max(legacy_candidates, key=subproject_version_key) if legacy_candidates else None


def ensure_default_code_root() -> Path:
    project = latest_model_project()
    if not project:
        raise FileNotFoundError(
            "Cannot find output/*_模型设计标准化. Run B04 to create or locate the 模型设计标准化 subproject first."
        )

    stable_code_dir = project / "03_代码程序"
    if stable_code_dir.exists():
        return stable_code_dir

    code_dirs = sorted(project.glob("03_代码程序_v*"))
    if not code_dirs:
        code_dir = stable_code_dir
        code_dir.mkdir(parents=True, exist_ok=True)
        return code_dir

    if len(code_dirs) == 1 and code_dirs[0].name.endswith("_v0.0.0"):
        has_content = any(code_dirs[0].iterdir())
        if not has_content:
            target = stable_code_dir
            code_dirs[0].rename(target)
            return target
    return code_dirs[-1]


def safe_task_name(name: str) -> str:
    stem = Path(name).stem
    stem = re.sub(r"^模型设计\s*[-_ ]*", "", stem)
    stem = re.sub(r"[^\w\u4e00-\u9fff]+", "", stem)
    return stem[:18] or "模型设计"


def create_run_dir(run_dir: str | None, output_root: str | None, task_name: str) -> Path:
    if run_dir:
        run_path = to_project_path(run_dir)
        ensure_dir(run_path)
        return run_path

    base = to_project_path(output_root) if output_root else ensure_default_code_root()
    runs_root = base / "runs"
    ensure_dir(runs_root)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + safe_task_name(task_name)
    run_path = runs_root / run_id
    ensure_dir(run_path)
    return run_path


def ensure_run_subdirs(run_dir: Path) -> None:
    for name in [
        "00_inputs",
        "01_parse",
        "02_ai_batches",
        "03_ai_decisions",
        "04_validation",
        "05_writeback",
        "06_deliverables",
    ]:
        ensure_dir(run_dir / name)


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(clean_text(v).replace("\n", "<br>") for v in row) + " |")
    return "\n".join(lines) + "\n"


def copy_file(src: Path | str, dst: Path | str) -> None:
    dst_path = Path(dst)
    ensure_dir(dst_path.parent)
    shutil.copy2(Path(src), dst_path)


def stringify_record(record: dict[str, Any]) -> str:
    return " ".join(clean_text(v) for v in record.values() if not isinstance(v, (dict, list)))
