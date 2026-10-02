#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import subprocess
from create_package import create_package

from validate_package import validate_package


SKILL_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_CASES = {
    "trigger-positive",
    "trigger-negative",
    "normal-flow",
    "time-pressure",
    "independence",
    "migration",
}
REQUIRED_RULES = {
    "SKILL.md": ["不把单个 `prototype.html`", "不因时间压力", "不依赖或路由任何外部系列"],
    "references/独立运行与迁移规则.md": ["HH 是临时系列", "ASOC 版本"],
}


def main() -> int:
    errors: list[str] = []
    cases = json.loads((SKILL_ROOT / "evaluation" / "test_cases.json").read_text(encoding="utf-8"))
    actual_cases = {item.get("id") for item in cases.get("cases", [])}
    missing = REQUIRED_CASES - actual_cases
    if missing:
        errors.append(f"缺少行为场景：{sorted(missing)}")
    for relative, phrases in REQUIRED_RULES.items():
        text = (SKILL_ROOT / relative).read_text(encoding="utf-8")
        for phrase in phrases:
            if phrase not in text:
                errors.append(f"{relative} 缺少约束：{phrase}")
    # The template is a scaffold, not a completed package with fabricated browser evidence.
    with tempfile.TemporaryDirectory(prefix="h01-contract-") as temporary:
        package = create_package(Path(temporary) / "package", "验证通用原型模板")
        checked = subprocess.run([sys.executable, str(SKILL_ROOT / "scripts/check_responsive.py"), str(package)])
        if checked.returncode:
            errors.append("新包真实浏览器响应式检查失败")
        errors.extend(validate_package(package, require_responsive=True))
    for error in errors:
        print(f"error={error}")
    print(f"contract_tests={'ok' if not errors else 'failed'}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
