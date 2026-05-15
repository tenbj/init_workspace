from __future__ import annotations

import argparse
from datetime import datetime

from e01_common import (
    markdown_table,
    read_json,
    read_jsonl,
    rel,
    to_project_path,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate E01 run summary markdown.")
    parser.add_argument("--run-dir", required=True)
    return parser.parse_args()


def count_jsonl(path) -> int:
    return len(read_jsonl(path)) if path.exists() else 0


def main() -> None:
    args = parse_args()
    run_dir = to_project_path(args.run_dir)
    manifest = read_json(run_dir / "run_manifest.json")
    template_check = read_json(run_dir / "01_parse" / "template_check.json") if (run_dir / "01_parse" / "template_check.json").exists() else {}
    validation = read_json(run_dir / "04_validation" / "validation_report.json") if (run_dir / "04_validation" / "validation_report.json").exists() else {}
    writeback_log = read_json(run_dir / "05_writeback" / "writeback_log.json") if (run_dir / "05_writeback" / "writeback_log.json").exists() else {}
    outputs = manifest.get("outputs", {})
    template_excel = outputs.get("template_writeback_excel", "")
    if not template_excel:
        matches = list((run_dir / "06_deliverables").glob("*_已标准化.xlsx"))
        template_excel = rel(matches[0]) if matches else ""

    counts = {
        "实体 sheet 数": count_jsonl(run_dir / "01_parse" / "entity_sheets.jsonl"),
        "字段行数": count_jsonl(run_dir / "01_parse" / "entity_fields.jsonl"),
        "跳过字段数": count_jsonl(run_dir / "02_ai_batches" / "skipped_fields.jsonl"),
        "AI 批次数": count_jsonl(run_dir / "02_ai_batches" / "ai_field_review_batches.jsonl"),
        "AI 字段决策数": count_jsonl(run_dir / "03_ai_decisions" / "ai_field_review_decisions.jsonl"),
        "待人工确认数": count_jsonl(run_dir / "04_validation" / "review_items.jsonl"),
        "待沉淀标准数": count_jsonl(run_dir / "03_ai_decisions" / "ai_standard_gaps.jsonl"),
        "模板检查问题数": template_check.get("issue_count", 0),
        "校验错误数": validation.get("counts", {}).get("error_count", 0),
        "校验警告数": validation.get("counts", {}).get("warning_count", 0),
    }

    deliverables = [
        ["建议版 Excel", rel(run_dir / "06_deliverables" / "模型设计标准化建议版.xlsx") if (run_dir / "06_deliverables" / "模型设计标准化建议版.xlsx").exists() else "未生成"],
        ["已标准化 Excel", template_excel or "未生成"],
        ["待人工确认清单", rel(run_dir / "06_deliverables" / "待人工确认清单.csv") if (run_dir / "06_deliverables" / "待人工确认清单.csv").exists() else "未生成"],
        ["待沉淀标准清单", rel(run_dir / "06_deliverables" / "待沉淀标准清单.csv") if (run_dir / "06_deliverables" / "待沉淀标准清单.csv").exists() else "未生成"],
        ["AI 批次索引", rel(run_dir / "02_ai_batches" / "batch_index.md") if (run_dir / "02_ai_batches" / "batch_index.md").exists() else "未生成"],
        ["校验摘要", rel(run_dir / "04_validation" / "validation_summary.md") if (run_dir / "04_validation" / "validation_summary.md").exists() else "未生成"],
    ]

    display_status = manifest.get("status", "unknown")
    if display_status == "writeback_completed":
        display_status = "completed"
    summary = [
        "# 模型设计标准化运行摘要",
        "",
        f"- 运行目录：`{rel(run_dir)}`",
        f"- 当前状态：`{display_status}`",
        f"- 模型设计：`{manifest.get('inputs', {}).get('model_design', '')}`",
        f"- 标准库：`{manifest.get('inputs', {}).get('standard_library', '')}`",
        f"- 生成时间：{datetime.now().isoformat(timespec='seconds')}",
        "",
        "## 统计",
        "",
        markdown_table(["指标", "值"], [[k, v] for k, v in counts.items()]),
        "",
        "## 交付物",
        "",
        markdown_table(["交付物", "路径"], deliverables),
    ]

    if template_check.get("issues"):
        summary.extend([
            "",
            "## 模板检查问题",
            "",
            markdown_table(
                ["级别", "sheet", "问题"],
                [[i.get("severity", ""), i.get("sheet_name", ""), i.get("issue", "")] for i in template_check["issues"]],
            ),
        ])

    if validation.get("issues"):
        summary.extend([
            "",
            "## 校验问题",
            "",
            markdown_table(
                ["级别", "范围", "类型", "问题"],
                [[i.get("severity", ""), i.get("scope", ""), i.get("issue_type", ""), i.get("issue", "")] for i in validation["issues"][:100]],
            ),
        ])

    if writeback_log:
        summary.extend([
            "",
            "## 回写结果",
            "",
            markdown_table(["指标", "值"], [[k, v] for k, v in writeback_log.items()]),
        ])

    content = "\n".join(summary).replace("\n\n\n", "\n\n")
    (run_dir / "run_summary.md").write_text(content, encoding="utf-8")
    (run_dir / "06_deliverables" / "模型设计标准化运行摘要.md").write_text(content, encoding="utf-8")

    manifest["outputs"]["summary"] = rel(run_dir / "run_summary.md")
    if manifest.get("status") in {"parsed", "validated", "writeback_completed"}:
        manifest["status"] = "summarized" if manifest["status"] != "writeback_completed" else "completed"
    from e01_common import write_json

    write_json(run_dir / "run_manifest.json", manifest)
    print(f"[OK] summary={rel(run_dir / 'run_summary.md')}")


if __name__ == "__main__":
    main()
