"""Shared responsive contract and evidence checks; no browser dependency."""
import hashlib
import json
from pathlib import Path

CAPABILITY = "responsive-web-v1"
REPORT = "evaluation/responsive-report.json"


def engine_fingerprint():
    root = Path(__file__).resolve().parent
    return hashlib.sha256((root / "responsive_contract.py").read_bytes() + (root / "check_responsive.py").read_bytes()).hexdigest()


def fingerprint(config):
    return hashlib.sha256(json.dumps(config, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def validate_config(config):
    if not isinstance(config, dict):
        return ["responsive: 必须定义响应式设计合同"]
    errors = []
    mode = config.get("mode")
    if mode not in ("adaptive", "desktop-only"):
        errors.append("responsive.mode: 仅支持adaptive或desktop-only")
    if mode == "desktop-only" and not str(config.get("reason", "")).strip():
        errors.append("responsive.reason: 仅桌面必须说明用户约束")
    bp = config.get("mobile_breakpoint", 700)
    if type(bp) is not int or not 430 <= bp <= 1024:
        errors.append("responsive.mobile_breakpoint: 必须为430至1024的整数")
    layouts = config.get("layouts", {})
    if not isinstance(layouts, dict) or not layouts.get("desktop") or (mode != "desktop-only" and not layouts.get("mobile")):
        errors.append("responsive.layouts: 必须说明目标平台的信息组织方式")
    ports = config.get("viewports", [])
    if not isinstance(ports, list) or not ports:
        errors.append("responsive.viewports: 不得为空")
        ports = []
    widths = set()
    for item in ports:
        if not isinstance(item, dict) or any(type(item.get(k)) is not int or item[k] <= 0 for k in ("width", "height")):
            errors.append("responsive.viewports: width/height必须为正整数")
        else:
            widths.add(item["width"])
    if mode == "adaptive" and not {360, 390, 430}.issubset(widths):
        errors.append("responsive.viewports: 缺少360/390/430px手机验收")
    if not any(w >= 1280 for w in widths):
        errors.append("responsive.viewports: 缺少桌面对照视口")
    scenarios = config.get("scenarios", [])
    if not isinstance(scenarios, list) or not scenarios:
        errors.append("responsive.scenarios: 至少定义一个核心操作场景")
        scenarios = []
    ids = set()
    for scenario in scenarios:
        if not isinstance(scenario, dict) or not isinstance(scenario.get("id"), str) or not scenario["id"] or scenario["id"] in ids:
            errors.append("responsive.scenarios: 场景ID缺失或重复")
            continue
        ids.add(scenario["id"])
        if not isinstance(scenario.get("requirement_ids"), list) or not scenario["requirement_ids"] or any(not isinstance(req, str) for req in scenario["requirement_ids"]):
            errors.append("responsive.scenarios: 必须关联REQ ID")
        steps = scenario.get("steps", [])
        if not isinstance(steps, list) or not steps:
            errors.append("responsive.scenarios: steps不得为空")
            continue
        actions = set()
        for step in steps:
            if not isinstance(step, dict) or not isinstance(step.get("selector"), str) or not step["selector"] or step.get("action") not in ("click", "fill", "select", "expect_visible", "expect_text"):
                errors.append("responsive.steps: 无效动作或缺少selector")
                continue
            actions.add(step["action"])
            if step["action"] in {"fill", "select", "expect_text"} and not isinstance(step.get("value"), str):
                errors.append("responsive.steps: 此动作必须提供字符串value")
        if not actions.intersection({"click", "fill", "select"}) or not actions.intersection({"expect_visible", "expect_text"}):
            errors.append("responsive.scenarios: 必须包含操作及可观察结果断言")
    return errors
