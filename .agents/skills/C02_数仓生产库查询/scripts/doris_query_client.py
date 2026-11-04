import os
import re
import importlib.util
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import pymysql
except ImportError:
    raise ImportError("缺少依赖：请先运行 `pip install pymysql` 再重试")

_WRITE_OPS = re.compile(
    # REPLACE(...) is a scalar string function; REPLACE INTO/table remains blocked.
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|GRANT|REVOKE|LOAD\s+DATA)\b"
    r"|\bREPLACE\b(?!\s*\()",
    re.IGNORECASE,
)
_DEFAULT_ROW_LIMIT = 500
_CONNECT_TIMEOUT = 10
_READ_TIMEOUT = 60
_WORKSPACE = Path(__file__).resolve().parents[4]


def _load_readonly_connection() -> Dict[str, str]:
    """只加载登记的 Doris 生产只读身份；不扫描旧文件或其他服务。"""
    loader = _WORKSPACE / ".envs" / "env_manager.py"
    if not loader.is_file():
        raise RuntimeError("缺少 .envs/env_manager.py，无法加载 doris.prod.readonly")
    spec = importlib.util.spec_from_file_location("_c02_env_manager", loader)
    manager = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(manager)
    values = manager.load_connection(_WORKSPACE, "doris.prod.readonly")
    if any(name in os.environ and os.environ[name] != value for name, value in values.items()):
        raise RuntimeError("当前进程环境与 doris.prod.readonly 冲突；请使用独立进程")
    return values


class DorisQueryClient:
    """生产库专用的查询引擎 (ReadOnly)

    特性：
    - 多库支持（database 参数，默认 cbebg）
    - SQL 安全守卫（拦截写操作/DDL）
    - 自动追加 LIMIT（防止 AI 查大表撑满 context）
    - 结构化返回（data / row_count / error 三段式）
    - Schema 探查方法（get_tables / describe_table）
    - EXPLAIN 支持（DWD SQL 开发调优）
    """

    def __init__(self, database: Optional[str] = None, row_limit: int = _DEFAULT_ROW_LIMIT):
        values = _load_readonly_connection()
        self.host = values["DORIS_HOST"]
        try:
            self.port = int(values["DORIS_PORT"])
        except ValueError:
            raise RuntimeError("DORIS_PORT 必须是整数") from None
        self.user = values["DORIS_USER"]
        self.password = values["DORIS_PASSWORD"]
        self.database = database or values["DORIS_DATABASE"]
        self.row_limit = row_limit

    # ── 内部工具 ────────────────────────────────────────────────────────────

    def _connect(self, database: Optional[str] = None):
        return pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=database or self.database,
            cursorclass=pymysql.cursors.DictCursor,
            charset="utf8mb4",
            connect_timeout=_CONNECT_TIMEOUT,
            read_timeout=_READ_TIMEOUT,
        )

    def _guard(self, sql: str) -> None:
        """拦截写操作和 DDL，防止 AI 误用。SHOW 语句始终只读，直接放行。"""
        if re.match(r"^\s*SHOW\b", sql, re.IGNORECASE):
            return
        match = _WRITE_OPS.search(sql)
        if match:
            raise ValueError(f"禁止写操作：检测到关键字 `{match.group()}`，本客户端仅支持只读查询。")

    def _inject_limit(self, sql: str) -> Tuple[str, bool]:
        """SELECT 语句若无 LIMIT，自动注入 row_limit。返回 (new_sql, injected)。"""
        stripped = sql.strip().rstrip(";")
        is_select = bool(re.search(r"^\s*(SELECT|WITH)\b", stripped, re.IGNORECASE))
        has_limit = bool(re.search(r"\bLIMIT\b", stripped, re.IGNORECASE))
        if is_select and not has_limit:
            return f"{stripped} LIMIT {self.row_limit}", True
        return stripped, False

    def _run(self, sql: str, database: Optional[str] = None) -> List[Dict]:
        conn = self._connect(database)
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
                return cur.fetchall()
        finally:
            conn.close()

    # ── 主查询接口 ──────────────────────────────────────────────────────────

    def query(self, sql: str, database: Optional[str] = None) -> Dict[str, Any]:
        """执行 SQL，返回结构化结果。

        Returns:
            {
                "data":         List[Dict],   # 行数据
                "row_count":    int,          # 实际返回行数
                "auto_limited": bool,         # 是否自动追加了 LIMIT
                "sql_executed": str,          # 实际执行的 SQL
                "error":        str | None    # 错误信息，成功时为 None
            }
        """
        try:
            self._guard(sql)
        except ValueError as e:
            return {"data": [], "row_count": 0, "auto_limited": False, "sql_executed": sql, "error": str(e)}

        final_sql, auto_limited = self._inject_limit(sql)
        try:
            rows = self._run(final_sql, database)
            return {
                "data": rows,
                "row_count": len(rows),
                "auto_limited": auto_limited,
                "sql_executed": final_sql,
                "error": None,
            }
        except pymysql.Error as e:
            return {
                "data": [],
                "row_count": 0,
                "auto_limited": auto_limited,
                "sql_executed": final_sql,
                "error": f"[DB {e.args[0]}] {e.args[1]}",
            }

    # ── Schema 探查 ─────────────────────────────────────────────────────────

    def get_databases(self) -> List[str]:
        """列出所有可用库名。"""
        rows = self._run("SHOW DATABASES")
        if not rows:
            return []
        key = list(rows[0].keys())[0]
        return [r[key] for r in rows]

    def get_tables(self, database: Optional[str] = None) -> List[str]:
        """列出指定库的所有表名。"""
        rows = self._run("SHOW TABLES", database or self.database)
        if not rows:
            return []
        key = list(rows[0].keys())[0]
        return [r[key] for r in rows]

    def describe_table(self, table: str, database: Optional[str] = None) -> List[Dict]:
        """获取表的字段结构（Field / Type / Null / Key / Default / Extra）。"""
        db = database or self.database
        return self._run(f"DESCRIBE `{db}`.`{table}`")

    def explain(self, sql: str, database: Optional[str] = None) -> str:
        """获取 SQL 执行计划，用于 DWD 开发调优。"""
        rows = self._run(f"EXPLAIN {sql.strip().rstrip(';')}", database)
        return "\n".join(str(list(r.values())[0]) for r in rows)

    # ── 格式化输出 ──────────────────────────────────────────────────────────

    @staticmethod
    def _cell(v: Any) -> str:
        return str(v).replace("|", "\\|").replace("\n", " ").replace("\r", "")

    def format_to_markdown_table(self, data: List[Dict[str, Any]]) -> str:
        if not data:
            return "_（无数据）_"
        keys = list(data[0].keys())
        lines = [
            "| " + " | ".join(self._cell(k) for k in keys) + " |",
            "|" + "|".join([":---"] * len(keys)) + "|",
        ]
        for row in data:
            lines.append("| " + " | ".join(self._cell(row.get(k, "")) for k in keys) + " |")
        return "\n".join(lines)

    def format_result(self, result: Dict[str, Any]) -> str:
        """将 query() 的结构化结果渲染为可读 Markdown（含元信息头）。"""
        if result.get("error"):
            return f"> **查询失败：** {result['error']}\n>\n> SQL：`{result['sql_executed']}`"

        lines = []
        if result["auto_limited"]:
            lines.append(f"> _结果已被截断至前 {self.row_limit} 行（SQL 未含 LIMIT）_\n")
        lines.append(f"**返回 {result['row_count']} 行**\n")
        lines.append(self.format_to_markdown_table(result["data"]))
        return "\n".join(lines)
