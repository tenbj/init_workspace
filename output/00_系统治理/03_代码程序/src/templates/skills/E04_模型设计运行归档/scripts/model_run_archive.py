#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


RUN_PREFIX = "E04"
PROJECT_TOPIC = "模型设计标准化"
REQUIRED_ROLES = {"standard_library", "model_design"}
INVALID_NAME_CHARS = r'[\\/:*?"<>|]'


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def timestamp_text() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M")


def safe_name(value: str) -> str:
    cleaned = re.sub(INVALID_NAME_CHARS, "_", value.strip())
    cleaned = re.sub(r"\s+", "_", cleaned)
    cleaned = cleaned.strip("._ ")
    return cleaned or "未命名"


def workspace_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "output").is_dir():
            return candidate
    raise RuntimeError("Output root not found.")


def is_under(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def ensure_under_output(path: Path, root: Path, label: str) -> Path:
    resolved = path.resolve()
    output_dir = (root / "output").resolve()
    if not is_under(resolved, output_dir):
        raise ValueError(f"{label} must be under output/: {resolved}")
    return resolved


def resolve_project_dir(root: Path, project_dir: str) -> Path:
    raw = Path(project_dir)
    candidates = [raw.resolve()] if raw.is_absolute() else [
        (root / raw).resolve(),
        (root / "output" / raw).resolve(),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ensure_under_output(candidate, root, "Project directory")
    raise FileNotFoundError(f"Project directory not found: {project_dir}")


def resolve_output_artifact(raw_path: str, run_dir: Path, root: Path, label: str) -> Path:
    raw = Path(raw_path)
    if raw.is_absolute():
        resolved = raw.resolve()
    elif raw.parts and raw.parts[0].lower() == "output":
        resolved = (root / raw).resolve()
    else:
        resolved = (run_dir / raw).resolve()
    return ensure_under_output(resolved, root, label)


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def rel_to(path: Path, base: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def parse_version(path: Path) -> tuple[int, int, int]:
    match = re.search(r"_v(\d+)\.(\d+)\.(\d+)$", path.name)
    if not match:
        return (0, 0, 0)
    return tuple(int(part) for part in match.groups())


def parse_project_number(path: Path) -> int:
    match = re.match(r"^(\d+)_", path.name)
    if not match:
        return 0
    return int(match.group(1))


def has_version_suffix(path: Path) -> bool:
    return re.search(r"_v\d+\.\d+\.\d+$", path.name) is not None


def find_model_projects(root: Path) -> list[Path]:
    output_dir = root / "output"
    if not output_dir.exists():
        return []
    return [
        item
        for item in output_dir.iterdir()
        if item.is_dir() and PROJECT_TOPIC in item.name
    ]


def newest_project(root: Path) -> Path | None:
    candidates = find_model_projects(root)
    if not candidates:
        return None
    return ensure_under_output(
        sorted(candidates, key=lambda item: (parse_project_number(item), parse_version(item), item.name), reverse=True)[0],
        root,
        "Project directory",
    )


def write_utf8_bom(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8-sig")


def read_utf8_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def memory_version(text: str) -> tuple[int, int, int]:
    match = re.search(r"<!--\s*memory-version:\s*(\d+)\.(\d+)\.(\d+)\s*-->", text)
    if not match:
        return (1, 0, 0)
    return tuple(int(part) for part in match.groups())


def update_global_knowledge_map(root: Path, topic: str, folder_name: str, created_date: str) -> None:
    memory_dir = root / ".memory"
    history_dir = root / ".history" / ".memory" / "全局知识地图"
    map_path = memory_dir / "全局知识地图.md"
    memory_dir.mkdir(parents=True, exist_ok=True)
    history_dir.mkdir(parents=True, exist_ok=True)
    row = f"| {topic} | {folder_name} | {created_date} | 进行中 | - |"

    if map_path.exists():
        map_text = read_utf8_text(map_path)
        old_version = memory_version(map_text)
        snapshot_path = history_dir / f"全局知识地图_v{old_version[0]}.{old_version[1]}.{old_version[2]}.md"
        shutil.copy2(map_path, snapshot_path)
        new_header = f"<!-- memory-version: {old_version[0]}.{old_version[1] + 1}.0 -->"
        if re.search(r"^\s*<!--\s*memory-version:\s*\d+\.\d+\.\d+\s*-->", map_text):
            map_text = re.sub(r"^\s*<!--\s*memory-version:\s*\d+\.\d+\.\d+\s*-->", new_header, map_text, count=1)
        else:
            map_text = f"{new_header}\n{map_text}"
    else:
        map_text = """<!-- memory-version: 1.0.0 -->
# 全局知识地图

> 所有研究子项目的总索引，新建子项目时自动更新。

| 话题 | 子项目文件夹 | 创建时间 | 状态 | 核心结论（一句话） |
|------|------------|---------|------|----------------|
"""

    if f"| {topic} | {folder_name} |" not in map_text:
        map_text = map_text.rstrip() + f"\n{row}\n"
    write_utf8_bom(map_path, map_text)


def initialize_conversation_record(root: Path, topic: str, folder_name: str) -> None:
    conv_path = root / ".memory" / "对话记录" / f"{folder_name}.md"
    if conv_path.exists():
        return
    write_utf8_bom(
        conv_path,
        f"""# 对话记录 · {topic}

> 记录本子项目所有对话的关键摘要，按时间追加。

---

""",
    )


def project_dir_candidates(root: Path, project_dir: str) -> list[Path]:
    raw = Path(project_dir)
    if raw.is_absolute():
        return [raw.resolve()]
    candidates = [(root / raw).resolve()]
    if not (raw.parts and raw.parts[0].lower() == "output"):
        candidates.append((root / "output" / raw).resolve())
    return candidates


def next_project_dir(root: Path) -> Path:
    output_dir = root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    numbers = [
        parse_project_number(item)
        for item in output_dir.iterdir()
        if item.is_dir() and parse_project_number(item) > 0
    ]
    next_number = (max(numbers) + 1) if numbers else 1
    return output_dir / f"{next_number:02d}_{PROJECT_TOPIC}"


def create_project_skeleton(project_dir: Path, root: Path) -> Path:
    if has_version_suffix(project_dir):
        raise ValueError(f"E04-created project directory must not end with a version suffix: {project_dir.name}")
    project_dir = ensure_under_output(project_dir, root, "Project directory")
    if project_dir.exists():
        return project_dir

    project_dir.mkdir(parents=True)
    for subdir in ["01_问题答疑_v0.0.0", "02_课题研究_v0.0.0", "03_代码程序_v0.0.0"]:
        (project_dir / subdir).mkdir()

    created_at = now_text()
    created_date = datetime.now().strftime("%Y-%m-%d")
    write_utf8_bom(
        project_dir / "版本记录.md",
        f"""# 版本记录 · {PROJECT_TOPIC}

> 记录子项目的版本变更历史。

---

## 初始创建 ({created_at})

**变更类型**：MAJOR
**创建时间**：{created_at}
**变更描述**：E04 自动创建模型设计标准化归档子项目，根目录不带版本号后缀。

**子文件变更明细**：

| 文件 | 版本变更 | 变更描述 |
|------|---------|---------|
| （待填写） | | |

---

""",
    )
    write_utf8_bom(
        project_dir / "目录.md",
        f"""# 目录 · {PROJECT_TOPIC}

> 本子项目内所有内容文件的索引，按三个子文件夹分节列出。

---

## 01_问题答疑

| # | 文件 | 说明 | 首次落盘 | 最近更新 |
|---|------|------|---------|---------|
| 待新增文件后填写 | | | | |

---

## 02_课题研究

| # | 文件 | 说明 | 首次落盘 | 最近更新 |
|---|------|------|---------|---------|
| 待新增文件后填写 | | | | |

---

## 03_代码程序

| # | 文件 | 说明 | 首次落盘 | 最近更新 |
|---|------|------|---------|---------|
| 待新增文件后填写 | | | | |

""",
    )
    update_global_knowledge_map(root, PROJECT_TOPIC, project_dir.name, created_date)
    initialize_conversation_record(root, PROJECT_TOPIC, project_dir.name)
    return project_dir


def create_model_project(root: Path, project_dir: str | None = None) -> Path:
    raise FileNotFoundError("请先按 B04 创建模型设计标准化子项目，再用 --project-dir 指定已有目录。")


def locate_project(root: Path, project_dir: str | None) -> Path:
    if project_dir:
        try:
            return resolve_project_dir(root, project_dir)
        except FileNotFoundError:
            return create_model_project(root, project_dir)

    project = newest_project(root)
    if project:
        return project
    return create_model_project(root)


def locate_code_dir(project_dir: Path) -> Path:
    code_dir = project_dir / "03_代码程序"
    code_dir.mkdir(parents=True, exist_ok=True)
    return code_dir


def unique_path(directory: Path, filename: str) -> Path:
    target = directory / filename
    if not target.exists():
        return target
    stem = target.stem
    suffix = target.suffix
    counter = 2
    while True:
        candidate = directory / f"{stem}_{counter:02d}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def unique_run_dir(run_root: Path, run_name: str, timestamp: str) -> tuple[str, Path]:
    base_id = f"{RUN_PREFIX}_{timestamp}_{safe_name(run_name)}"
    run_dir = run_root / base_id
    if not run_dir.exists():
        return base_id, run_dir
    counter = 2
    while True:
        run_id = f"{base_id}_{counter:02d}"
        candidate = run_root / run_id
        if not candidate.exists():
            return run_id, candidate
        counter += 1


def same_drive(source: Path, target: Path) -> bool:
    source_drive = source.resolve().drive.lower()
    target_drive = target.resolve().drive.lower()
    if source_drive or target_drive:
        return source_drive == target_drive
    return True


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_input(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise ValueError(f"Input must use role=path: {value}")
    role, raw_path = value.split("=", 1)
    role = role.strip()
    if not role:
        raise ValueError(f"Input role is empty: {value}")
    return role, Path(raw_path.strip().strip('"'))


def archive_one(role: str, source: Path, run_dir: Path, root: Path, mode: str) -> dict[str, Any]:
    source = source.resolve()
    if not source.exists():
        raise FileNotFoundError(f"Input not found for {role}: {source}")
    if not source.is_file():
        raise ValueError(f"Input is not a file for {role}: {source}")

    archive_dir = run_dir / "00_inputs" / "source_archive"
    copy_dir = run_dir / "00_inputs" / "source_copy"
    move_reason = ""
    storage_mode = "copy"

    if mode == "copy":
        destination = unique_path(copy_dir, source.name)
        shutil.copy2(source, destination)
    elif mode == "move":
        if not same_drive(source, run_dir):
            raise RuntimeError(f"Cannot move cross-drive input for {role}: {source}")
        destination = unique_path(archive_dir, source.name)
        shutil.move(str(source), str(destination))
        storage_mode = "move"
    else:
        if same_drive(source, run_dir):
            destination = unique_path(archive_dir, source.name)
            try:
                shutil.move(str(source), str(destination))
                storage_mode = "move"
            except Exception as exc:  # noqa: BLE001 - failure reason is persisted for recovery.
                move_reason = str(exc)
                destination = unique_path(copy_dir, source.name)
                shutil.copy2(source, destination)
        else:
            move_reason = "cross-drive input; copied instead of moved"
            destination = unique_path(copy_dir, source.name)
            shutil.copy2(source, destination)

    return {
        "source_name": source.name,
        "effective_path": rel_to(destination, run_dir),
        "effective_abs_path": str(destination.resolve()),
        "storage_mode": storage_mode,
        "sha256": sha256_file(destination),
        "size_bytes": destination.stat().st_size,
        "move_fallback_reason": move_reason,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_summary(run_dir: Path, context: dict[str, Any]) -> None:
    status = context.get("status", "prepared")
    inputs = context.get("inputs", {})
    deliverables = context.get("deliverables", [])
    message = context.get("message", "")

    input_rows = []
    for role, item in inputs.items():
        input_rows.append(
            f"| `{role}` | `{item.get('storage_mode', '')}` | `{item.get('effective_path', '')}` | `{item.get('sha256', '')}` |"
        )
    if not input_rows:
        input_rows.append("| - | - | - | - |")

    deliverable_rows = []
    for item in deliverables:
        deliverable_rows.append(
            f"| `{item.get('path', '')}` | {item.get('exists', False)} | {item.get('size_bytes', 0)} |"
        )
    if not deliverable_rows:
        deliverable_rows.append("| - | - | - |")

    content = f"""# E04 运行摘要 · {context.get('run_id', '')}

> status: {status}
> updated-at: {context.get('updated_at', '')}

---

## 路径

| 项 | 路径 |
|------|------|
| run_dir | `{context.get('run_dir', '')}` |
| run_context | `{context.get('paths', {}).get('run_context', 'run_context.json')}` |
| prepare_result | `{context.get('paths', {}).get('prepare_result', '')}` |
| context_json | `{context.get('paths', {}).get('context_json', '')}` |
| recommendations_json | `{context.get('paths', {}).get('recommendations_json', '')}` |
| deliverable_excel | `{context.get('paths', {}).get('deliverable_excel', '')}` |

## 输入

| role | storage | effective_path | sha256 |
|------|------|------|------|
{chr(10).join(input_rows)}

## 交付物

| 路径 | exists | size_bytes |
|------|------|------|
{chr(10).join(deliverable_rows)}

## 备注

{message or "无"}
"""
    (run_dir / "run_summary.md").write_text(content, encoding="utf-8")


def prepare(args: argparse.Namespace) -> int:
    root = workspace_root(Path(__file__))
    project_dir = locate_project(root, args.project_dir)
    code_dir = locate_code_dir(project_dir)
    run_root = code_dir / "runs"
    run_root.mkdir(parents=True, exist_ok=True)
    run_id, run_dir = unique_run_dir(run_root, args.run_name, args.timestamp or timestamp_text())

    for subdir in [
        "00_inputs/source_archive",
        "00_inputs/source_copy",
        "01_parse",
        "03_ai_decisions",
        "06_deliverables",
    ]:
        (run_dir / subdir).mkdir(parents=True, exist_ok=True)

    parsed_inputs = dict(parse_input(item) for item in args.input)
    missing = REQUIRED_ROLES - set(parsed_inputs)
    if missing:
        raise ValueError(f"Missing required input role(s): {', '.join(sorted(missing))}")

    archived_inputs = {
        role: archive_one(role, source, run_dir, root, args.archive_mode)
        for role, source in parsed_inputs.items()
    }

    created_at = now_text()
    manifest = {
        "schema_version": "1.0.0",
        "created_at": created_at,
        "archive_mode_requested": args.archive_mode,
        "inputs": archived_inputs,
    }
    manifest_path = run_dir / "00_inputs" / "input_manifest.json"
    write_json(manifest_path, manifest)

    safe_run = safe_name(args.run_name)
    context = {
        "schema_version": "1.0.0",
        "skill_id": "E04",
        "target_skill_id": args.target_skill,
        "run_id": run_id,
        "project_dir": rel(project_dir, root),
        "run_dir": rel(run_dir, root),
        "layout_mode": "managed_project",
        "inputs": {
            role: {
                key: value
                for key, value in item.items()
                if key in {"source_name", "effective_path", "storage_mode", "sha256", "size_bytes", "move_fallback_reason"}
            }
            for role, item in archived_inputs.items()
        },
        "paths": {
            "input_manifest": rel_to(manifest_path, run_dir),
            "context_json": "01_parse/context.json",
            "prepare_result": "01_parse/prepare_result.json",
            "recommendations_json": "03_ai_decisions/recommendations.json",
            "deliverable_excel": f"06_deliverables/{safe_run}_命名建议.xlsx",
            "run_context": "run_context.json",
            "run_summary": "run_summary.md",
        },
        "deliverables": [],
        "status": "prepared",
        "created_at": created_at,
        "updated_at": created_at,
        "message": "准备完成，等待 E03 抽取、AI 决策和 Excel 写回。",
    }
    context_path = run_dir / "run_context.json"
    write_json(context_path, context)
    write_summary(run_dir, context)

    result = {
        "schema_version": "1.0.0",
        "status": "prepared",
        "run_id": run_id,
        "project_dir": str(project_dir.resolve()),
        "run_dir": str(run_dir.resolve()),
        "run_context_path": str(context_path.resolve()),
        "run_summary_path": str((run_dir / "run_summary.md").resolve()),
        "standard_library_path": archived_inputs["standard_library"]["effective_abs_path"],
        "model_design_path": archived_inputs["model_design"]["effective_abs_path"],
        "context_json_path": str((run_dir / context["paths"]["context_json"]).resolve()),
        "recommendations_json_path": str((run_dir / context["paths"]["recommendations_json"]).resolve()),
        "deliverable_excel_path": str((run_dir / context["paths"]["deliverable_excel"]).resolve()),
    }
    out_path = resolve_output_artifact(args.out, run_dir, root, "--out") if args.out else run_dir / context["paths"]["prepare_result"]
    result["prepare_result_path"] = str(out_path.resolve())
    write_json(out_path, result)

    print(f"run_id={run_id}")
    print(f"run_dir={run_dir.resolve()}")
    print(f"run_context={context_path.resolve()}")
    print(f"prepare_result={out_path.resolve()}")
    return 0


def finalize(args: argparse.Namespace) -> int:
    context_path = Path(args.run_context).resolve()
    if not context_path.exists():
        raise FileNotFoundError(context_path)
    run_dir = context_path.parent
    context = read_json(context_path)
    if args.status == "completed":
        if not args.deliverable:
            raise ValueError("completed requires at least one --deliverable file.")
        for item in args.deliverable:
            path = Path(item)
            full_path = (run_dir / path).resolve() if not path.is_absolute() else path.resolve()
            if not full_path.is_file():
                raise FileNotFoundError(f"Cannot complete run: deliverable file not found: {full_path}")
    context["status"] = args.status
    context["updated_at"] = now_text()
    context["message"] = args.message or ("运行完成。" if args.status == "completed" else "运行失败，需查看上游错误。")

    deliverables = []
    for item in args.deliverable or []:
        path = Path(item)
        full_path = (run_dir / path).resolve() if not path.is_absolute() else path.resolve()
        deliverables.append(
            {
                "path": rel_to(full_path, run_dir),
                "exists": full_path.exists(),
                "size_bytes": full_path.stat().st_size if full_path.exists() else 0,
            }
        )
    if deliverables:
        context["deliverables"] = deliverables

    if args.status == "completed":
        context["completed_at"] = context["updated_at"]
    elif args.status == "failed":
        context["failed_at"] = context["updated_at"]

    write_json(context_path, context)
    write_summary(run_dir, context)
    print(f"status={args.status}")
    print(f"run_context={context_path}")
    print(f"run_summary={run_dir / 'run_summary.md'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare and finalize archived E04 runs for E03 model naming.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare", help="Archive inputs and create run context.")
    prepare_parser.add_argument("--target-skill", default="E03", help="Target skill stable id, default: E03")
    prepare_parser.add_argument("--run-name", required=True, help="Business name used in run id and deliverable name.")
    prepare_parser.add_argument("--input", action="append", required=True, help="Input in role=path form. Requires standard_library and model_design.")
    prepare_parser.add_argument("--project-dir", help="Model design standardization project directory.")
    prepare_parser.add_argument("--archive-mode", choices=["move-or-copy", "copy", "move"], default="move-or-copy")
    prepare_parser.add_argument("--timestamp", help="Override timestamp for deterministic tests, format yyyyMMdd_HHmm.")
    prepare_parser.add_argument("--out", help="Write prepare result JSON to this path.")
    prepare_parser.set_defaults(func=prepare)

    finalize_parser = subparsers.add_parser("finalize", help="Update run context and summary after E03 finishes.")
    finalize_parser.add_argument("--run-context", required=True, help="Path to run_context.json")
    finalize_parser.add_argument("--status", choices=["completed", "failed"], required=True)
    finalize_parser.add_argument("--deliverable", action="append", help="Deliverable path, absolute or relative to run dir.")
    finalize_parser.add_argument("--message", help="Summary message or failure reason.")
    finalize_parser.set_defaults(func=finalize)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except Exception as exc:
        print(f"error={exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
