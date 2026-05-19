from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
from typing import Any

from e01_common import (
    clean_text,
    markdown_table,
    read_json,
    read_jsonl,
    rel,
    stringify_record,
    to_project_path,
    write_jsonl,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build AI review batches from parsed E01 artifacts.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--max-standard-rows", type=int, default=200)
    return parser.parse_args()


def contains_context(record: dict[str, Any], needles: list[str]) -> bool:
    text = stringify_record(record)
    return any(needle and needle in text for needle in needles)


def catalog_for_sheet(catalog: list[dict[str, Any]], sheet_name: str, declared_table: str) -> list[dict[str, Any]]:
    return [
        row for row in catalog
        if contains_context(row, [sheet_name, declared_table])
    ]


def dependency_for_sheet(dependency_rows: list[dict[str, Any]], sheet_name: str, declared_table: str) -> list[dict[str, Any]]:
    return [
        row for row in dependency_rows
        if contains_context(row, [sheet_name, declared_table])
    ]


def flag_value(value: Any) -> str:
    return clean_text(value).strip().lower()


def is_negative_retention(value: Any) -> bool:
    text = flag_value(value)
    return text in {"否", "不", "不保留", "删除", "false", "0", "n", "no"}


def is_positive_deletion(value: Any) -> bool:
    text = flag_value(value)
    return text in {"是", "删除", "需删除", "true", "1", "y", "yes"}


def should_skip_field(field: dict[str, Any]) -> tuple[bool, str]:
    if is_negative_retention(field.get("is_retained")):
        return True, "是否保留=否"
    if is_positive_deletion(field.get("is_deleted")):
        return True, "是否删除=是"
    return False, ""


def make_decision_templates(fields_by_sheet: dict[str, list[dict[str, Any]]], entity_sheets: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    field_templates: list[dict[str, Any]] = []
    for sheet_name, fields in fields_by_sheet.items():
        for field in fields:
            field_templates.append({
                "sheet_name": sheet_name,
                "row_number": field["row_number"],
                "current_field_name": field.get("field_name", ""),
                "recommended_field_name": "",
                "decision": "",
                "confidence": "",
                "reason": "",
                "human_question": "",
                "writeback_allowed": False,
            })

    table_templates = [
        {
            "sheet_name": sheet["sheet_name"],
            "current_table_name": sheet.get("declared_table", ""),
            "recommended_table_name": "",
            "decision": "",
            "confidence": "",
            "reason": "",
            "human_question": "",
        }
        for sheet in entity_sheets
    ]
    return field_templates, table_templates


def main() -> None:
    args = parse_args()
    run_dir = to_project_path(args.run_dir)
    if not run_dir.exists():
        raise FileNotFoundError(run_dir)

    entity_sheets = read_jsonl(run_dir / "01_parse" / "entity_sheets.jsonl")
    entity_fields = read_jsonl(run_dir / "01_parse" / "entity_fields.jsonl")
    catalog = read_json(run_dir / "01_parse" / "model_catalog.json")
    dependency = read_json(run_dir / "01_parse" / "dependency_raw.json")
    standard = read_json(run_dir / "01_parse" / "standard_library_raw.json")

    fields_by_sheet: dict[str, list[dict[str, Any]]] = defaultdict(list)
    skipped_fields: list[dict[str, Any]] = []
    for field in entity_fields:
        skip, reason = should_skip_field(field)
        if skip:
            skipped_fields.append({
                "sheet_name": field.get("sheet_name", ""),
                "row_number": field.get("row_number", ""),
                "current_field_name": field.get("field_name", ""),
                "field_desc": field.get("field_desc", ""),
                "is_retained": field.get("is_retained", ""),
                "is_deleted": field.get("is_deleted", ""),
                "skip_reason": reason,
            })
            continue
        fields_by_sheet[field["sheet_name"]].append(field)

    sheet_lookup = {sheet["sheet_name"]: sheet for sheet in entity_sheets}
    standard_context = {
        "rules": standard.get("rules", [])[:args.max_standard_rows],
        "mappings": standard.get("mappings", [])[:args.max_standard_rows],
        "note": "标准库是 AI 权威参考资料，不是脚本语义规则。",
    }

    batches: list[dict[str, Any]] = []
    for sheet_name, fields in fields_by_sheet.items():
        sheet = sheet_lookup.get(sheet_name, {})
        declared_table = sheet.get("declared_table", "")
        batches.append({
            "batch_id": f"entity:{sheet_name}",
            "sheet_name": sheet_name,
            "declared_table": declared_table,
            "instructions": {
                "goal": "全量评审本实体 sheet 的字段命名、字段描述、参考字段、参考库表和标准库符合度。",
                "script_boundary": "脚本只按 Excel 显式控制标识跳过字段：是否保留=否、是否删除=是；其余语义判断交给 AI。",
                "field_control_policy": "fields 中的 is_enum_field 来自 Excel 的“是否为枚举字段”，有值时必须以表格记录为准，不要自行反向猜测或覆盖该枚举标识。",
                "language": "输出给人看的 reason、human_question、suggested_standard、gap reason 必须使用中文；表名和字段名作为技术标识可保留英文。",
                "output_schema": "见 references/ai_decision_schema.md",
            },
            "model_context": {
                "entity_sheet": sheet,
                "catalog_rows": catalog_for_sheet(catalog, sheet_name, declared_table),
                "dependency_rows": dependency_for_sheet(dependency, sheet_name, declared_table),
            },
            "standard_library_context": standard_context,
            "fields": fields,
        })

    write_jsonl(run_dir / "02_ai_batches" / "ai_field_review_batches.jsonl", batches)
    write_jsonl(run_dir / "02_ai_batches" / "skipped_fields.jsonl", skipped_fields)

    index_rows = []
    for batch in batches:
        index_rows.append([
            batch["batch_id"],
            batch["sheet_name"],
            batch.get("declared_table", ""),
            len(batch["fields"]),
            "待 AI 评审",
        ])
    batch_index = "# AI 批次索引\n\n" + markdown_table(
        ["batch_id", "sheet", "declared_table", "字段行数", "状态"],
        index_rows,
    )
    (run_dir / "02_ai_batches" / "batch_index.md").write_text(batch_index, encoding="utf-8")

    field_templates, table_templates = make_decision_templates(fields_by_sheet, entity_sheets)
    write_jsonl(run_dir / "03_ai_decisions" / "ai_field_review_decisions.template.jsonl", field_templates)
    write_jsonl(run_dir / "03_ai_decisions" / "ai_table_review_decisions.template.jsonl", table_templates)
    write_jsonl(run_dir / "03_ai_decisions" / "ai_standard_gaps.template.jsonl", [])

    summary = [
        "# AI 决策填写说明",
        "",
        f"- 工作包：`{rel(run_dir / '02_ai_batches' / 'ai_field_review_batches.jsonl')}`",
        f"- 跳过字段清单：`{rel(run_dir / '02_ai_batches' / 'skipped_fields.jsonl')}`，来源为 `是否保留=否` 或 `是否删除=是`。",
        f"- 字段决策模板：`{rel(run_dir / '03_ai_decisions' / 'ai_field_review_decisions.template.jsonl')}`",
        "- 请复制模板内容，填充后保存为 `ai_field_review_decisions.jsonl`。",
        "- 表名决策保存为 `ai_table_review_decisions.jsonl`。",
        "- 标准缺口保存为 `ai_standard_gaps.jsonl`，没有缺口时可为空文件。",
        "- 所有给人看的说明、问题、建议、待沉淀原因必须写中文；表名和字段名作为技术标识可保留英文。",
        "",
    ]
    (run_dir / "03_ai_decisions" / "ai_decision_summary.md").write_text("\n".join(summary), encoding="utf-8")

    print(f"[OK] batches={len(batches)}")
    print(f"[OK] field_decision_template_rows={len(field_templates)}")
    print(f"[OK] skipped_fields={len(skipped_fields)}")
    print(f"[OK] batch_index={rel(run_dir / '02_ai_batches' / 'batch_index.md')}")


if __name__ == "__main__":
    main()
