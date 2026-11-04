import os
import importlib.util
from pathlib import Path
from typing import List, Dict, Any

try:
    import pymysql
except ImportError:
    raise ImportError("缺少依赖：请先运行 `pip install pymysql` 再重试")

_WORKSPACE = Path(__file__).resolve().parents[4]


def _load_test_connection() -> Dict[str, str]:
    loader = _WORKSPACE / ".envs" / "env_manager.py"
    if not loader.is_file():
        raise RuntimeError("缺少 .envs/env_manager.py，无法加载 doris.test.writer")
    spec = importlib.util.spec_from_file_location("_c04_env_manager", loader)
    manager = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(manager)
    values = manager.load_connection(_WORKSPACE, "doris.test.writer")
    if any(name in os.environ and os.environ[name] != value for name, value in values.items()):
        raise RuntimeError("当前进程环境与 doris.test.writer 冲突；请使用独立进程")
    if values["DORIS_DATABASE"] != "test":
        raise RuntimeError("doris.test.writer 的 DORIS_DATABASE 必须为 test")
    return values


class DorisStorageClient:
    """测试库专属的存储构建引擎 (Read/Write)"""
    def __init__(self):
        values = _load_test_connection()
        self.host = values["DORIS_HOST"]
        try:
            self.port = int(values["DORIS_PORT"])
        except ValueError:
            raise RuntimeError("DORIS_PORT 必须是整数") from None
        self.user = values["DORIS_USER"]
        self.password = values["DORIS_PASSWORD"]
        self.db = values["DORIS_DATABASE"]

    def get_connection(self):
        return pymysql.connect(
            host=self.host, port=self.port, user=self.user, password=self.password, 
            database=self.db, cursorclass=pymysql.cursors.DictCursor, charset="utf8mb4"
        )

    def execute(self, sql: str, params: tuple = None) -> int:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                result = cursor.execute(sql, params)
                conn.commit()
                return result
        finally:
            conn.close()
            
    def execute_many(self, sql: str, params_list: List[tuple]) -> int:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                result = cursor.executemany(sql, params_list)
                conn.commit()
                return result
        finally:
            conn.close()
