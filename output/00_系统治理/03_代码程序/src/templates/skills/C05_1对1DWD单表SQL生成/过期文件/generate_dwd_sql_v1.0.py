#!/usr/bin/env python3
"""
DWD 单表 SQL 生成脚本

用法：
    python generate_dwd_sql.py <ods_table_name>

示例：
    python generate_dwd_sql.py cbebg.ods_realtime_db_t_lx_newad_hasadgroups

输出：
    <project_root>/output/C05_1对1DWD单表SQL生成/<dwd_table_name>/<dwd_table_name>.sql
    <project_root>/output/C05_1对1DWD单表SQL生成/<dwd_table_name>/<dwd_table_name>.md  （有异常时）
"""

import argparse
import io
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from pathlib import Path

# ── 路径配置 ───────────────────────────────────────────────────────────────────
SCRIPT_DIR   = Path(__file__).parent.resolve()
# 脚本位于 .agents/skills/C05_1对1DWD单表SQL生成/scripts/，向上 4 级到项目根目录
PROJECT_ROOT = SCRIPT_DIR.parents[3]
OUTPUT_DIR   = PROJECT_ROOT / "output" / "1对1DWD单表SQL生成"

# ODS SQL 源码目录，如路径不对修改此处
DATA_ASSETS_DIR = PROJECT_ROOT / "权威资料" / "data-assets"

TARGET_SCHEMA   = "cbebg"
DIM_SHOP_TABLE  = "glcd.dim_shop_ich_dd"
DIM_MSKU_TABLE  = "glcd.dim_msku_ich_dd"

# ── 字段分类触发词 ─────────────────────────────────────────────────────────────
ENUM_SUFFIXES = (
    "_type", "_status", "_code", "_flag",
    "_level", "_state", "_mode", "_kind", "_category",
)
TIMESTAMP_KEYWORDS = ("_time", "_at", "_ts", "timestamp")
AUDIT_FIELDS = {"first_inserted_dt", "etl_dt", "last_updated_dt"}

# ── 维表触发信号 ───────────────────────────────────────────────────────────────
DIM_SHOP_SIGNALS = {
    "sid":          ("DIM-SHOP-002", "lx_shop_id"),
    "lx_shop_id":   ("DIM-SHOP-002", "lx_shop_id"),
    "shopid":       ("DIM-SHOP-001", "saas_shop_id"),
    "saas_shop_id": ("DIM-SHOP-001", "saas_shop_id"),
}

# ── 域前缀 ─────────────────────────────────────────────────────────────────────
KNOWN_DOMAINS = [
    "ads", "trd", "inv", "fl", "fin", "mkt",
    "op", "cs", "cst", "crm",
]


# ──────────────────────────────────────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────────────────────────────────────

def to_snake(name: str) -> str:
    """camelCase / PascalCase → snake_case"""
    s = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s).lower()


def strip_schema(table: str) -> str:
    return table.split(".")[-1]


def find_ods_sql(table_name: str) -> Path | None:
    bare = strip_schema(table_name)
    for pattern in [f"{bare}.sql", f"*{bare}*.sql"]:
        hits = list(DATA_ASSETS_DIR.rglob(pattern))
        if hits:
            return hits[0]
    return None


# ──────────────────────────────────────────────────────────────────────────────
# ODS SQL 解析
# ──────────────────────────────────────────────────────────────────────────────

def detect_load_strategy(sql: str) -> tuple[str, str | None]:
    """Returns (strategy, time_field)"""
    if re.search(r"\$\{(StartTime|EndTime|bizdate)\}", sql, re.IGNORECASE):
        m = re.search(
            r"CAST\s*\(\s*(?:\w+\.)?(\w+)\s+as\s+Date\s*\)",
            sql, re.IGNORECASE
        )
        return "ilu", (m.group(1) if m else None)
    return "flu", None


def extract_columns_from_ddl(sql: str) -> list[str]:
    """从 CREATE TABLE 提取列名"""
    m = re.search(r"CREATE\s+TABLE\s+\S+\s*\((.*?)\)", sql, re.IGNORECASE | re.DOTALL)
    if not m:
        return []
    cols = []
    for line in m.group(1).splitlines():
        line = line.strip().rstrip(",")
        if not line or line.upper().startswith(("PRIMARY", "KEY", "INDEX", "UNIQUE")):
            continue
        col = line.split()[0].strip("`\"'")
        if col:
            cols.append(col)
    return cols


def extract_select_exprs(sql: str) -> list[str]:
    """从 SELECT...FROM 提取字段表达式，处理括号嵌套"""
    m = re.search(r"\bSELECT\b(.*?)\bFROM\b", sql, re.IGNORECASE | re.DOTALL)
    if not m:
        return []
    raw = m.group(1).strip()
    fields, depth, current = [], 0, ""
    for ch in raw:
        if ch == "(":
            depth += 1
            current += ch
        elif ch == ")":
            depth -= 1
            current += ch
        elif ch == "," and depth == 0:
            fields.append(current.strip())
            current = ""
        else:
            current += ch
    if current.strip():
        fields.append(current.strip())
    return fields


_SQL_KEYWORDS = {
    "then", "else", "end", "when", "and", "or", "not",
    "null", "true", "false", "from", "where", "on",
    "by", "asc", "desc", "case", "select", "join",
}

def parse_alias(expr: str) -> tuple[str, str]:
    """
    Returns (expr_body, alias)
    支持显式 AS 别名和隐式别名（末尾标识符）。
    """
    # 显式 AS 别名
    m = re.match(r"^(.*?)\s+as\s+(\w+)\s*$", expr, re.IGNORECASE)
    if m:
        return m.group(1).strip(), m.group(2).strip()

    # 隐式别名：末尾是简单标识符且不是 SQL 关键字
    m2 = re.match(r"^(.*)\s+(\w+)$", expr.strip())
    if m2:
        body, last = m2.group(1).strip(), m2.group(2)
        if last.lower() not in _SQL_KEYWORDS and body:
            return body, last

    # 单列标识符，无别名
    m3 = re.match(r"^(?:\w+\.)?(\w+)$", expr.strip())
    alias = m3.group(1) if m3 else re.sub(r"\W+", "_", expr.strip())
    return expr.strip(), alias


# ──────────────────────────────────────────────────────────────────────────────
# DWD 表名推导
# ──────────────────────────────────────────────────────────────────────────────

ODS_PREFIXES = [
    "ods_realtime_db_t_",
    "ods_realtime_",
    "ods_sync_",
    "ods_api_",
    "ods_",
]

def derive_dwd_name(ods_table: str, strategy: str) -> str:
    bare = strip_schema(ods_table)
    biz = bare
    for prefix in ODS_PREFIXES:
        if biz.startswith(prefix):
            biz = biz[len(prefix):]
            break

    domain = None
    for d in KNOWN_DOMAINS:
        if biz.startswith(d + "_"):
            domain = d
            break
    if domain is None:
        domain = biz.split("_")[0]
        print(f"    ⚠️  无法识别域前缀，默认使用 '{domain}'，请人工确认 DWD 表名")

    suffix = "ilu" if strategy == "ilu" else "flu"
    return f"{TARGET_SCHEMA}.dwd_{biz}_{suffix}_dd"


# ──────────────────────────────────────────────────────────────────────────────
# 维表关联
# ──────────────────────────────────────────────────────────────────────────────

def build_shop_join(src_field: str, dim_field: str) -> str:
    return (
        f"left join (\n"
        f"    select {dim_field}, shop_id\n"
        f"    from {DIM_SHOP_TABLE}\n"
        f"    where is_valid = 1\n"
        f") dim_shop\n"
        f"    on src.{src_field} = dim_shop.{dim_field}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# SQL 生成
# ──────────────────────────────────────────────────────────────────────────────

INDENT = "    "

def build_sql(
    dwd_table: str,
    ods_bare: str,
    strategy: str,
    time_field: str | None,
    target_fields: list[str],
    select_exprs: list[str],
    join_sql: str,
    enum_fields: list[str],
    warnings: list[str],
) -> str:
    target_block = ",\n".join(f"{INDENT}{f}" for f in target_fields)
    select_block  = ",\n".join(f"{INDENT}{e}" for e in select_exprs)
    audit_block   = (
        f"{INDENT}NOW() as first_inserted_dt,\n"
        f"{INDENT}NOW() as etl_dt,\n"
        f"{INDENT}NOW() as last_updated_dt"
    )
    join_part = f"\n{join_sql}" if join_sql else ""

    header_lines = []
    if enum_fields:
        header_lines.append(
            f"-- ⚠️ ENUM_FIELDS: {', '.join(enum_fields)}\n"
            f"-- LLM请为以上字段判断是否需要补充 _desc 列"
        )
    for w in warnings:
        header_lines.append(f"-- ⚠️  {w}")
    header = ("\n".join(header_lines) + "\n\n") if header_lines else ""

    if strategy == "flu":
        return (
            f"{header}"
            f"insert overwrite table {dwd_table}\n"
            f"(\n{target_block}\n)\n"
            f"select\n{select_block},\n{audit_block}\n"
            f"from {TARGET_SCHEMA}.{ods_bare} src{join_part};\n"
        )
    else:
        tf = time_field or "biz_date"
        return (
            f"{header}"
            f"delete from {dwd_table}\n"
            f"where CAST({tf} as Date) >= '${{StartTime}}'\n"
            f"  and CAST({tf} as Date) <= '${{EndTime}}';\n\n"
            f"insert into {dwd_table}\n"
            f"(\n{target_block}\n)\n"
            f"select\n{select_block},\n{audit_block}\n"
            f"from {TARGET_SCHEMA}.{ods_bare} src{join_part}\n"
            f"where CAST(src.{tf} as Date) >= '${{StartTime}}'\n"
            f"  and CAST(src.{tf} as Date) <= '${{EndTime}}';\n"
        )


# ──────────────────────────────────────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="DWD 单表 SQL 生成")
    parser.add_argument("ods_table", help="ODS 表名，如 cbebg.ods_realtime_db_t_lx_newad_xxx")
    args = parser.parse_args()
    ods_table = args.ods_table

    # 确保输出目录存在
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: 找 ODS SQL 文件
    print(f"[1/6] 查找 ODS SQL：{ods_table}")
    sql_path = find_ods_sql(ods_table)
    if not sql_path:
        print(f"❌ 找不到 ODS SQL 文件\n    搜索路径：{DATA_ASSETS_DIR}")
        sys.exit(1)
    print(f"     → {sql_path.name}")
    ods_sql = sql_path.read_text(encoding="utf-8", errors="ignore")

    # Step 2: 装载策略
    print("[2/6] 判断装载策略")
    strategy, time_field = detect_load_strategy(ods_sql)
    print(f"     → {strategy.upper()}，时间字段：{time_field or '未检测到'}")

    # Step 3: DWD 表名
    print("[3/6] 推导 DWD 表名")
    dwd_table = derive_dwd_name(ods_table, strategy)
    print(f"     → {dwd_table}")

    # Step 4: 解析字段
    print("[4/6] 解析字段列表")
    columns_from_ddl = extract_columns_from_ddl(ods_sql)
    select_raw = extract_select_exprs(ods_sql)

    if not columns_from_ddl and not select_raw:
        print("❌ 无法从 ODS SQL 中提取字段列表")
        sys.exit(1)

    source_exprs = select_raw if select_raw else columns_from_ddl
    print(f"     → 提取 {len(source_exprs)} 个字段表达式")

    sql_upper = ods_sql.upper()
    for kw in ("LATERAL VIEW", "EXPLODE", "GROUP BY"):
        if kw in sql_upper:
            print(f"❌ ODS SQL 含 '{kw}'，不在一对一生成范围，退出")
            sys.exit(1)

    target_fields:  list[str] = []
    select_exprs:   list[str] = []
    enum_fields:    list[str] = []
    warnings:       list[str] = []
    dim_archive:    str | None = None
    dim_src_field:  str | None = None
    dim_dim_field:  str | None = None
    has_asin = False

    for raw in source_exprs:
        expr, alias = parse_alias(raw)
        alias_lower = alias.lower()

        # 跳过审计字段
        if alias_lower in AUDIT_FIELDS:
            continue

        # snake_case 修正
        norm = to_snake(alias)

        # 时间戳修正（FIELD-006）
        bare_col = re.sub(r"^\w+\.", "", expr)
        if (
            any(kw in norm for kw in TIMESTAMP_KEYWORDS)
            and "from_unixtime" not in expr.lower()
            and "date" not in norm
        ):
            new_expr = f"from_unixtime(src.{bare_col} / 1000)"
            select_exprs.append(f"{new_expr} as {norm}")
            target_fields.append(norm)
            print(f"     [FIELD-006] 时间戳修正：{alias} → from_unixtime({bare_col}/1000)")
            continue

        # 维表触发信号
        if dim_archive is None and norm in DIM_SHOP_SIGNALS:
            dim_archive, dim_dim_field = DIM_SHOP_SIGNALS[norm]
            dim_src_field = norm
            print(f"     [DIM] 命中 {dim_archive}，关联字段：{norm} → {dim_dim_field}")

        if norm == "asin":
            has_asin = True

        # 枚举字段检测
        if any(norm.endswith(sfx) for sfx in ENUM_SUFFIXES):
            enum_fields.append(norm)

        # 生成 SELECT 表达式
        if alias != norm:
            select_exprs.append(f"src.{bare_col} as {norm}")
        else:
            select_exprs.append(f"src.{bare_col}")
        target_fields.append(norm)

    # 维表字段插入
    join_sql = ""
    if dim_archive and dim_src_field:
        join_sql = build_shop_join(dim_src_field, dim_dim_field)
        try:
            insert_pos = target_fields.index(dim_src_field) + 1
        except ValueError:
            insert_pos = 1
        target_fields.insert(insert_pos, "shop_id")
        select_exprs.insert(insert_pos, "dim_shop.shop_id")

    if has_asin and dim_archive in ("DIM-SHOP-001", "DIM-SHOP-002"):
        warnings.append("检测到 asin 字段 + shop_id，疑似需要 DIM-MSKU-001，请人工确认")

    if not dim_archive:
        warnings.append("未检测到标准维表触发信号，如需维表关联请人工确认")

    target_fields += ["first_inserted_dt", "etl_dt", "last_updated_dt"]

    print(f"     → 共 {len(target_fields)} 个目标字段，枚举候选：{enum_fields or '无'}")

    # Step 5: 生成 SQL
    print("[5/6] 生成 SQL")
    sql = build_sql(
        dwd_table    = dwd_table,
        ods_bare     = strip_schema(ods_table),
        strategy     = strategy,
        time_field   = time_field,
        target_fields= target_fields,
        select_exprs = select_exprs,
        join_sql     = join_sql,
        enum_fields  = enum_fields,
        warnings     = warnings,
    )

    # Step 6: 写文件
    print("[6/6] 写入输出文件")
    dwd_bare = strip_schema(dwd_table)
    table_dir = OUTPUT_DIR / dwd_bare
    table_dir.mkdir(parents=True, exist_ok=True)
    out_sql = table_dir / f"{dwd_bare}.sql"
    out_sql.write_text(sql, encoding="utf-8")
    print(f"     → {out_sql}")

    # 异常写 .md
    issues: list[str] = []
    if enum_fields:
        issues.append(f"枚举候选字段（需补充 _desc 映射）：{', '.join(enum_fields)}")
    for w in warnings:
        issues.append(w)

    if issues:
        md_lines = ["# 异常说明\n\n## 需人工处理\n\n"]
        for i in issues:
            md_lines.append(f"- {i}\n")
        out_md = table_dir / f"{dwd_bare}.md"
        out_md.write_text("".join(md_lines), encoding="utf-8")
        print(f"     → {out_md}")

    print(f"\nOUTPUT_DIR={table_dir}")


if __name__ == "__main__":
    main()
