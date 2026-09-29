#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

import jsonschema
import yaml


REQUIRED_FILES = [
    "manifest.json",
    "prd.md",
    "prototype.html",
    "ui.schema.json",
    "interaction.json",
    "user-flow.md",
    "api.yaml",
    "database.sql",
]
SKILL_ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path, errors: list[str]) -> object | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path.name}: JSON 无法解析：{exc}")
        return None


def validate_package(root: Path) -> list[str]:
    errors: list[str] = []
    for relative in REQUIRED_FILES:
        if not (root / relative).is_file():
            errors.append(f"缺少必备产物：{relative}")
    if errors:
        return errors

    manifest = load_json(root / "manifest.json", errors)
    ui = load_json(root / "ui.schema.json", errors)
    interaction = load_json(root / "interaction.json", errors)
    if errors:
        return errors

    if not isinstance(manifest, dict) or not manifest.get("intent"):
        errors.append("manifest.json: intent 不能为空")
    manifest_paths = {
        item.get("path")
        for item in manifest.get("artifacts", [])
        if isinstance(item, dict)
    } if isinstance(manifest, dict) else set()
    for relative in [*REQUIRED_FILES[1:], "evaluation/report.json"]:
        if relative not in manifest_paths:
            errors.append(f"manifest.json: 未登记 {relative}")

    prd = (root / "prd.md").read_text(encoding="utf-8")
    if not re.search(r"\bREQ-\d{3,}\b", prd):
        errors.append("prd.md: 至少需要一个 REQ-xxx 需求 ID")

    components = ui.get("components", []) if isinstance(ui, dict) else []
    page_states = set(ui.get("page", {}).get("states", [])) if isinstance(ui, dict) else set()
    component_ids = {
        item.get("id") for item in components if isinstance(item, dict) and item.get("id")
    }
    interactions = (
        interaction.get("interactions", []) if isinstance(interaction, dict) else []
    )
    interaction_by_id = {
        item.get("id"): item
        for item in interactions
        if isinstance(item, dict) and item.get("id")
    }

    for component in components:
        if not isinstance(component, dict):
            continue
        for event_id in component.get("events", []):
            if event_id not in interaction_by_id:
                errors.append(f"ui.schema.json: 未定义事件 {event_id}")

    for event_id, item in interaction_by_id.items():
        if item.get("component_id") not in component_ids:
            errors.append(f"interaction.json: {event_id} 引用了不存在的组件")
        for key in ("from_state", "to_state"):
            state = item.get(key)
            if state and state not in page_states:
                errors.append(f"interaction.json: {event_id} 的 {key}={state} 未在页面状态中定义")

    html = (root / "prototype.html").read_text(encoding="utf-8")
    buttons = re.findall(r"<button\b[^>]*>", html, flags=re.IGNORECASE)
    for button in buttons:
        if not re.search(r'data-event-id\s*=\s*["\'][^"\']+["\']', button, re.IGNORECASE):
            errors.append("prototype.html: button 缺少 data-event-id")
    html_event_ids = set(
        re.findall(r'data-event-id\s*=\s*["\']([^"\']+)["\']', html, re.IGNORECASE)
    )
    for event_id in html_event_ids:
        if event_id not in interaction_by_id:
            errors.append(f"prototype.html: data-event-id={event_id} 未在 interaction.json 定义")
    scripts = "\n".join(
        re.findall(r"<script\b[^>]*>(.*?)</script>", html, flags=re.IGNORECASE | re.DOTALL)
    )
    for event_id in interaction_by_id:
        if event_id not in html_event_ids:
            errors.append(f"interaction.json: 事件 {event_id} 未绑定到 prototype.html")
        elif event_id not in scripts or "addEventListener" not in scripts:
            errors.append(f"prototype.html: 事件 {event_id} 缺少 JavaScript 绑定")

    flow = (root / "user-flow.md").read_text(encoding="utf-8")
    if "START" not in flow or "END" not in flow:
        errors.append("user-flow.md: 必须包含 START 和 END")

    api_text = (root / "api.yaml").read_text(encoding="utf-8")
    try:
        api = yaml.safe_load(api_text)
    except yaml.YAMLError as exc:
        api = None
        errors.append(f"api.yaml: YAML 无法解析：{exc}")
    api_na = isinstance(api, dict) and api.get("x-asoc-not-applicable") is True
    if not api_na and isinstance(api, dict):
        if not isinstance(api.get("openapi"), str):
            errors.append("api.yaml: 缺少有效 openapi 版本")
        paths = api.get("paths")
        if not isinstance(paths, dict) or not paths:
            errors.append("api.yaml: paths 必须是非空对象")
        else:
            operations = [
                operation
                for path_item in paths.values()
                if isinstance(path_item, dict)
                for method, operation in path_item.items()
                if method.lower() in {"get", "post", "put", "patch", "delete"}
                and isinstance(operation, dict)
            ]
            if not operations:
                errors.append("api.yaml: 至少定义一个 HTTP operation")
            elif not any(
                any(str(code).startswith(("4", "5")) for code in operation.get("responses", {}))
                for operation in operations
                if isinstance(operation.get("responses"), dict)
            ):
                errors.append("api.yaml: 至少定义一个 4xx/5xx 错误响应")
    elif not api_na and api is not None:
        errors.append("api.yaml: 根节点必须是对象")

    database = (root / "database.sql").read_text(encoding="utf-8")
    if "CREATE TABLE" not in database.upper() and "ASOC-NOT-APPLICABLE:" not in database.upper():
        errors.append("database.sql: 缺少 CREATE TABLE 或 ASOC-NOT-APPLICABLE 标记")

    if isinstance(manifest, dict):
        output_schema = json.loads((SKILL_ROOT / "output.schema.json").read_text(encoding="utf-8"))
        output_instance = {
            "package_dir": str(root),
            "artifacts": manifest.get("artifacts", []),
            "evaluation": {"valid": True, "report": "evaluation/report.json"},
        }
        try:
            jsonschema.validate(output_instance, output_schema)
        except jsonschema.ValidationError as exc:
            errors.append(f"output.schema.json: {exc.message}")
    return errors


def write_report(path: Path, errors: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "asoc_version": "1.0.0",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "valid": not errors,
        "errors": errors,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="验证 H01 原型能力包。")
    parser.add_argument("package_dir", help="待验证的原型能力包目录")
    parser.add_argument("--report", help="验证报告路径")
    args = parser.parse_args()
    root = Path(args.package_dir).resolve()
    errors = validate_package(root)
    report = Path(args.report).resolve() if args.report else root / "evaluation" / "report.json"
    write_report(report, errors)
    for error in errors:
        print(f"error={error}")
    print(f"report={report}")
    print(f"package_validation={'ok' if not errors else 'failed'}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
