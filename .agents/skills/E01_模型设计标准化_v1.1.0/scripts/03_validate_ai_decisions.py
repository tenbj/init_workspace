from __future__ import annotations

import argparse
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from e01_common import (
    CONFIDENCES,
    DECISIONS,
    clean_text,
    markdown_table,
    read_json,
    read_jsonl,
    rel,
    to_project_path,
    write_json,
    write_jsonl,
)


FIELD_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate AI decision JSONL files for E01.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--allow-missing", action="store_true")
    parser.add_argument("--mode", default="review_only", choices=["review_only", "template_writeback"])
    return parser.parse_args()


def as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
    return None


def issue(severity: str, scope: str, issue_type: str, message: str, **extra: Any) -> dict[str, Any]:
    return {
        "severity": severity,
        "scope": scope,
        "issue_type": issue_type,
        "issue": message,
        **extra,
    }


def validate_field_decisions(run_dir: Path, allow_missing: bool, mode: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    review_items: list[dict[str, Any]] = []
    decisions_path = run_dir / "03_ai_decisions" / "ai_field_review_decisions.jsonl"
    fields = read_jsonl(run_dir / "01_parse" / "entity_fields.jsonl")
    skipped = read_jsonl(run_dir / "02_ai_batches" / "skipped_fields.jsonl")
    skipped_keys = {(f["sheet_name"], int(f["row_number"])) for f in skipped}
    expected = {
        (f["sheet_name"], int(f["row_number"]))
        for f in fields
        if (f["sheet_name"], int(f["row_number"])) not in skipped_keys
    }

    if not decisions_path.exists():
        severity = "warning" if allow_missing else "error"
        issues.append(issue(
            severity,
            "run",
            "missing_field_decisions",
            "缺少 AI 字段决策文件",
            expected_path=rel(decisions_path),
        ))
        return [], issues, review_items

    decisions = read_jsonl(decisions_path)
    seen: set[tuple[str, int]] = set()
    names_by_sheet: dict[str, list[str]] = defaultdict(list)
    required_keys = [
        "sheet_name",
        "row_number",
        "current_field_name",
        "recommended_field_name",
        "decision",
        "confidence",
        "reason",
        "writeback_allowed",
    ]

    for idx, row in enumerate(decisions, 1):
        missing = [key for key in required_keys if key not in row]
        if missing:
            issues.append(issue("error", "field_decision", "missing_keys", "字段决策缺少必填字段", line=idx, missing_keys=missing))
            continue

        sheet = clean_text(row.get("sheet_name"))
        try:
            row_number = int(row.get("row_number"))
        except (TypeError, ValueError):
            issues.append(issue("error", "field_decision", "invalid_row_number", "row_number 不是整数", line=idx, value=row.get("row_number")))
            continue

        key = (sheet, row_number)
        seen.add(key)
        if key not in expected:
            issues.append(issue("warning", "field_decision", "unexpected_field_row", "AI 决策指向未解析到的字段行", sheet_name=sheet, row_number=row_number))

        decision = clean_text(row.get("decision"))
        confidence = clean_text(row.get("confidence"))
        recommended = clean_text(row.get("recommended_field_name"))
        reason = clean_text(row.get("reason"))
        writeback_allowed = as_bool(row.get("writeback_allowed"))

        if decision not in DECISIONS:
            issues.append(issue("error", "field_decision", "invalid_decision", "非法 decision", sheet_name=sheet, row_number=row_number, value=decision))
        if confidence not in CONFIDENCES:
            issues.append(issue("error", "field_decision", "invalid_confidence", "非法 confidence", sheet_name=sheet, row_number=row_number, value=confidence))
        if not reason:
            issues.append(issue("error", "field_decision", "missing_reason", "AI 决策缺少 reason", sheet_name=sheet, row_number=row_number))
        if writeback_allowed is None:
            issues.append(issue("error", "field_decision", "invalid_writeback_allowed", "writeback_allowed 必须是布尔值", sheet_name=sheet, row_number=row_number))

        if recommended:
            if not FIELD_NAME_RE.match(recommended) or "__" in recommended:
                issues.append(issue("warning", "field_decision", "field_name_format", "推荐字段名不符合小写下划线格式", sheet_name=sheet, row_number=row_number, value=recommended))
            names_by_sheet[sheet].append(recommended)

        if writeback_allowed:
            if mode == "review_only" and (decision != "fill_safe" or confidence != "high" or not recommended):
                issues.append(issue("error", "field_decision", "unsafe_writeback", "review_only 下 writeback_allowed=true 仅允许 high 置信度 fill_safe 且必须有推荐字段名", sheet_name=sheet, row_number=row_number))
            if mode == "template_writeback" and (decision not in {"keep", "fill_safe", "replace_suggestion"} or confidence not in {"high", "medium"} or not recommended):
                issues.append(issue("error", "field_decision", "unsafe_writeback", "template_writeback 下 writeback_allowed=true 仅允许 keep/fill_safe/replace_suggestion 且置信度不能为 low", sheet_name=sheet, row_number=row_number))

        if decision in {"suggest_with_review", "replace_suggestion", "need_human_confirm", "cannot_decide"}:
            review_items.append({
                "severity": "error" if decision == "cannot_decide" else "warning",
                "scope": "field",
                "sheet_name": sheet,
                "row_number": row_number,
                "issue_type": decision,
                "issue": clean_text(row.get("human_question")) or reason,
                "suggestion": recommended,
                "ai_reason": reason,
            })

    missing_rows = sorted(expected - seen)
    for sheet, row_number in missing_rows:
        issues.append(issue("error", "field_decision", "missing_field_row_decision", "AI 字段决策未覆盖解析字段行", sheet_name=sheet, row_number=row_number))

    for sheet, names in names_by_sheet.items():
        for name, count in Counter(n for n in names if n).items():
            if count > 1:
                issues.append(issue("warning", "field_decision", "duplicate_recommended_field", "同一实体内推荐字段名重复", sheet_name=sheet, value=name, count=count))

    return decisions, issues, review_items


def validate_standard_gaps(run_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    path = run_dir / "03_ai_decisions" / "ai_standard_gaps.jsonl"
    if not path.exists():
        return [], []
    gaps = read_jsonl(path)
    issues: list[dict[str, Any]] = []
    for idx, gap in enumerate(gaps, 1):
        for key in ["gap_type", "source_sheet", "suggested_standard", "reason", "status"]:
            if not clean_text(gap.get(key)):
                issues.append(issue("warning", "standard_gap", "missing_gap_key", "待沉淀标准缺少字段", line=idx, missing_key=key))
    return gaps, issues


def main() -> None:
    args = parse_args()
    run_dir = to_project_path(args.run_dir)
    if not run_dir.exists():
        raise FileNotFoundError(run_dir)

    decisions, field_issues, review_items = validate_field_decisions(run_dir, args.allow_missing, args.mode)
    gaps, gap_issues = validate_standard_gaps(run_dir)
    issues = field_issues + gap_issues
    errors = [i for i in issues if i["severity"] == "error"]
    warnings = [i for i in issues if i["severity"] == "warning"]

    report = {
        "status": "failed" if errors else "passed",
        "mode": args.mode,
        "counts": {
            "field_decision_count": len(decisions),
            "skipped_field_count": len(read_jsonl(run_dir / "02_ai_batches" / "skipped_fields.jsonl")),
            "standard_gap_count": len(gaps),
            "review_item_count": len(review_items),
            "error_count": len(errors),
            "warning_count": len(warnings),
        },
        "issues": issues,
    }

    write_json(run_dir / "04_validation" / "validation_report.json", report)
    write_jsonl(run_dir / "04_validation" / "review_items.jsonl", review_items)

    summary_rows = [
        ["字段决策数", len(decisions)],
        ["跳过字段数", report["counts"]["skipped_field_count"]],
        ["待沉淀标准数", len(gaps)],
        ["待人工确认数", len(review_items)],
        ["错误数", len(errors)],
        ["警告数", len(warnings)],
    ]
    summary = "# AI 决策校验摘要\n\n" + markdown_table(["指标", "值"], summary_rows)
    if issues:
        summary += "\n## 问题\n\n" + markdown_table(
            ["级别", "范围", "类型", "问题"],
            [[i["severity"], i["scope"], i["issue_type"], i["issue"]] for i in issues[:200]],
        )
    (run_dir / "04_validation" / "validation_summary.md").write_text(summary, encoding="utf-8")

    manifest_path = run_dir / "run_manifest.json"
    if manifest_path.exists():
        manifest = read_json(manifest_path)
        manifest["status"] = "validated" if not errors else "validation_failed"
        manifest["validation"] = report["counts"]
        write_json(manifest_path, manifest)

    print(f"[OK] validation_status={report['status']}")
    print(f"[OK] errors={len(errors)} warnings={len(warnings)} review_items={len(review_items)}")
    if errors and not args.allow_missing:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
