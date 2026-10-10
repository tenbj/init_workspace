"""
查询 Doris 建表语句并保存到本地 SQL 文件。

用法：
    python get_create_table.py <表名>
    python get_create_table.py <库名.表名>
    python get_create_table.py <库名.表名> --output-dir <目录>

示例：
    python get_create_table.py ods_realtime_db_t_lx_newad_portfolios
    python get_create_table.py cbebg.ods_realtime_db_t_lx_newad_portfolios
    python get_create_table.py glcd.dim_shop_ich_dd --output-dir D:/my_output

不指定库名时默认使用 cbebg。
--output-dir 为必填参数，不指定时脚本报错退出。
"""

import sys
import io
import pathlib
import importlib.util
import datetime
import argparse
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

SCRIPT_DIR   = pathlib.Path(__file__).parent.resolve()
PROJECT_ROOT = next((parent for parent in SCRIPT_DIR.parents
                     if (parent / ".system/standards/workspace-spec.json").is_file()), None)
if PROJECT_ROOT is None:
    raise RuntimeError("找不到当前工作区注册表")
# DEFAULT_OUT 不再提供默认值，必须通过 --output-dir 参数指定
# 避免绕过子项目管理 Skill 在 output/ 下创建不合规文件夹
DEFAULT_DB   = "cbebg"

_registry = json.loads((PROJECT_ROOT / ".system/standards/workspace-spec.json").read_text(encoding="utf-8-sig"))["skillsManagement"]["registeredSkills"]
_matches = [name for name in _registry if name.startswith("C02_")]
if len(_matches) != 1:
    raise RuntimeError("C02 注册表解析失败：必须唯一匹配")
DORIS_CLIENT = PROJECT_ROOT / ".agents" / "skills" / _matches[0] / "scripts" / "doris_query_client.py"


def load_client():
    if not DORIS_CLIENT.exists():
        print(f"[ERROR] 找不到 doris_query_client.py，路径：{DORIS_CLIENT}", file=sys.stderr)
        sys.exit(1)
    spec = importlib.util.spec_from_file_location("doris_query_client", DORIS_CLIENT)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.DorisQueryClient


def parse_table_arg(raw: str):
    if "." in raw:
        parts = raw.split(".", 1)
        return parts[0].strip(), parts[1].strip()
    return DEFAULT_DB, raw.strip()


def get_create_table_sql(database: str, table: str) -> str:
    DorisQueryClient = load_client()
    client = DorisQueryClient(database=database)
    sql    = f"SHOW CREATE TABLE `{database}`.`{table}`"
    print(f"[INFO] 执行：{sql}")
    result = client.query(sql, database=database)
    if result["error"]:
        print(f"[ERROR] 查询失败：{result['error']}", file=sys.stderr)
        sys.exit(1)
    rows = result["data"]
    if not rows:
        print("[ERROR] 返回结果为空", file=sys.stderr)
        sys.exit(1)
    row = rows[0]
    return row.get("Create Table") or list(row.values())[-1]


def save_sql(database: str, table: str, create_sql: str, output_dir: pathlib.Path) -> pathlib.Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename  = f"{database}.{table}_{timestamp}.sql"
    out_path  = output_dir / filename
    content   = (
        f"-- Source: SHOW CREATE TABLE {database}.{table}\n"
        f"-- Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"{create_sql};\n"
    )
    out_path.write_text(content, encoding="utf-8")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="查询 Doris 建表语句")
    parser.add_argument("table", help="表名（格式：表名 或 库名.表名）")
    parser.add_argument("--output-dir", required=True, help="输出目录（必填）")
    args = parser.parse_args()

    database, table = parse_table_arg(args.table)
    output_dir      = pathlib.Path(args.output_dir)

    print(f"[INFO] 库：{database}  表：{table}")
    create_sql = get_create_table_sql(database, table)
    out_path   = save_sql(database, table, create_sql, output_dir)

    print(f"[OK] 建表语句已保存：{out_path}")
    print("-" * 60)
    print(create_sql)


if __name__ == "__main__":
    main()
