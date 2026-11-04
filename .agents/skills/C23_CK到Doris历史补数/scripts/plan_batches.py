"""Offline date-window planner; no database access and no execution authorization.

Usage: python plan_batches.py daily.json --max-rows 5000000 --output batches.json
Input: {"evidence": "path or evidence description", "queried_at": "timestamp",
        "days": [{"date": "2022-11-01", "ck_count": 100, "doris_count": 20,
                  "missing_count": 80, "historical_candidate": true,
                  "safe_to_reload": true}]}
The caller must have independently verified missing record frequencies, absence
from the actual Doris source, and lossless reconstruction of deleted Doris rows.
Include every candidate-history day, including days already complete in Doris.
NULL dates, unsafe windows and single days above capacity are blocked, not split.
Defaults describe candidate history; executable windows describe current gaps.
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
import json
from pathlib import Path
import re


def plan(data: dict, max_rows: int = 5_000_000) -> dict:
    if type(max_rows) is not int or max_rows <= 0:
        raise ValueError("max_rows must be a positive integer")
    if not isinstance(data, dict):
        raise ValueError("input must be an object")
    for field in ("evidence", "queried_at"):
        if not isinstance(data.get(field), str) or not data[field].strip():
            raise ValueError(f"{field} is required")
    if not isinstance(data.get("days"), list):
        raise ValueError("days must be a list")
    rows, seen, blocked = [], set(), []
    for raw in data["days"]:
        if not isinstance(raw, dict):
            raise ValueError("each day must be an object")
        row = dict(raw)
        for field in ("ck_count", "doris_count", "missing_count"):
            if type(row.get(field)) is not int or row[field] < 0:
                raise ValueError(f"{field} must be a nonnegative integer")
        for field in ("historical_candidate", "safe_to_reload"):
            if type(row.get(field)) is not bool:
                raise ValueError(f"{field} must be a boolean")
        if row["missing_count"] > row["ck_count"]:
            raise ValueError("missing_count exceeds ck_count")
        value = row.get("date")
        if value is not None:
            if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise ValueError("date must be YYYY-MM-DD or null")
            date.fromisoformat(value)
        if value in seen:
            raise ValueError(f"duplicate date: {value}")
        seen.add(value)
        rows.append(row)

    candidates = sorted(r["date"] for r in rows if r["date"] is not None
                        and r["historical_candidate"] and r["ck_count"] > 0)
    batches, current, previous = [], None, None
    for row in sorted(rows, key=lambda r: r["date"] or ""):
        if row["missing_count"] == 0:
            continue
        reason = None
        if row["date"] is None:
            reason = "NULL date requires a separate confirmed plan"
        elif not row["historical_candidate"]:
            reason = "gap is not verified candidate history"
        elif not row["safe_to_reload"]:
            reason = "lossless reconstruction of deleted rows is not verified"
        elif row["ck_count"] > max_rows:
            reason = "single-day rewrite exceeds capacity; two dates cannot split it"
        if reason:
            blocked.append({"date": row["date"], "reason": reason,
                            "missing_count": row["missing_count"],
                            "read_rows": row["ck_count"]})
            continue
        day = date.fromisoformat(row["date"])
        adjacent = previous is not None and day == previous + timedelta(days=1)
        if current is None or not adjacent or current["read_rows"] + row["ck_count"] > max_rows:
            current = {"StartTime": row["date"], "EndTime": row["date"],
                       "read_rows": 0, "write_rows": 0, "delete_rows": 0,
                       "missing_rows": 0}
            batches.append(current)
        current["EndTime"] = row["date"]
        current["read_rows"] += row["ck_count"]
        current["write_rows"] += row["ck_count"]
        current["delete_rows"] += row["doris_count"]
        current["missing_rows"] += row["missing_count"]
        previous = day
    return {"evidence": data["evidence"], "queried_at": data["queried_at"],
            "max_rows": max_rows, "requires_scope_confirmation": True,
            "status": "blocked" if blocked else "draft",
            "defaults": {"StartTime": candidates[0] if candidates else None,
                         "EndTime": candidates[-1] if candidates else None},
            "batches": batches, "blocked": blocked,
            "missing_rows": sum(r["missing_count"] for r in rows)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--max-rows", type=int, default=5_000_000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error("input and output must differ")
    try:
        result = plan(json.loads(args.input.read_text(encoding="utf-8-sig")), args.max_rows)
    except (ValueError, TypeError) as exc:
        parser.error(str(exc))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "batches": len(result["batches"]),
                      "blocked": len(result["blocked"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
