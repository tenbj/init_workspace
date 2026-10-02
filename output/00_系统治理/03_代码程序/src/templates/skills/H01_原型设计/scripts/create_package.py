#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import jsonschema


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "assets" / "prototype-package"
INPUT_SCHEMA = Path(__file__).resolve().parents[1] / "input.schema.json"


def load_input(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    schema = json.loads(INPUT_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.validate(payload, schema)
    return payload


def create_package(output: Path, intent: str, input_payload: dict | None = None) -> Path:
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"输出目录非空，拒绝覆盖：{output}")
    output.mkdir(parents=True, exist_ok=True)
    shutil.copytree(TEMPLATE_DIR, output, dirs_exist_ok=True)
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["intent"] = input_payload["intent"] if input_payload else intent
    if input_payload:
        manifest["input"] = input_payload
    ui_path = output / "ui.schema.json"
    ui = json.loads(ui_path.read_text(encoding="utf-8"))
    policy = (input_payload or {}).get("responsive", {})
    if policy.get("mode") == "desktop-only" and not policy.get("reason") and (input_payload or {}).get("target_platform") != "desktop":
        raise ValueError("排除移动端必须给出用户约束reason")
    if (input_payload or {}).get("target_platform") == "desktop" or policy.get("mode") == "desktop-only":
        ui["responsive"]["mode"] = "desktop-only"
        ui["responsive"]["reason"] = policy.get("reason") or "用户输入明确指定target_platform=desktop"
        ui["responsive"]["viewports"] = [{"width": 1440, "height": 1000}]
    ui_path.write_text(json.dumps(ui, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="初始化 H01 原型能力包。")
    parser.add_argument("--output", required=True, help="能力包输出目录")
    parser.add_argument("--intent", default="待补充产品意图", help="写入 manifest 的 Intent")
    parser.add_argument("--input", help="符合 input.schema.json 的输入 JSON")
    args = parser.parse_args()
    try:
        input_payload = load_input(Path(args.input).resolve()) if args.input else None
        created = create_package(Path(args.output).resolve(), args.intent, input_payload)
    except (ValueError, OSError, json.JSONDecodeError, jsonschema.ValidationError) as exc:
        print(f"error={exc}")
        return 1
    print(f"created={created}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
