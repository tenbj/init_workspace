#!/usr/bin/env python3
"""只读导出命名手册所有非空单元格，避免错误尺寸元数据漏读。"""
import argparse
import hashlib
import json
from pathlib import Path
from openpyxl import load_workbook


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', default=str(Path(__file__).resolve().parents[1] / 'assets/数仓_01_命名规范手册.xlsx'))
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    src, out = Path(args.input).resolve(), Path(args.output).resolve()
    if src == out or out.suffix.lower() != '.json':
        parser.error('输出为独立JSON，不能覆盖原手册')
    wb = load_workbook(src, read_only=True, data_only=True)
    sheets = {}
    try:
        for sheet in wb:
            sheet.reset_dimensions()
            sheets[sheet.title] = {cell.coordinate: cell.value for row in sheet for cell in row if cell.value is not None}
    finally:
        wb.close()
    result = {'source': str(src), 'sha256': hashlib.sha256(src.read_bytes()).hexdigest(), 'sheets': sheets}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    print(json.dumps({'sheets': len(sheets), 'nonempty_cells': sum(map(len, sheets.values()))}))


if __name__ == '__main__':
    main()
