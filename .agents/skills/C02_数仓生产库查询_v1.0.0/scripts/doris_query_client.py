import os
import re
from typing import Any, Dict, List, Optional, Tuple

try:
    import pymysql
except ImportError:
    raise ImportError("缺少依赖：请先运行 `pip install pymysql` 再重试")

_WRITE_OPS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|REPLACE|GRANT|REVOKE|LOAD\s+DATA)\b",
    re.IGNORECASE,
)
_DEFAULT_ROW_LIMIT = 500
_CONNECT_TIMEOUT = 10
_READ_TIMEOUT = 60


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"缺少环境变量：{name}")
    return value


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"环境变量 {name} 必须是整数") from exc


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
        self.host = _required_env("DORIS_QUERY_HOST")
        self.port = _int_env("DORIS_QUERY_PORT", 9030)
        self.user = _required_env("DORIS_QUERY_USER")
        self.password = _required_env("DORIS_QUERY_PASSWORD")
        self.database = database or os.getenv("DORIS_QUERY_DEFAULT_DB", "cbebg")
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
