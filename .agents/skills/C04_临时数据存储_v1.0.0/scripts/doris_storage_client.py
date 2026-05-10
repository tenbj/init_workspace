import os
from typing import List, Dict, Any

try:
    import pymysql
except ImportError:
    raise ImportError("缺少依赖：请先运行 `pip install pymysql` 再重试")

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


class DorisStorageClient:
    """测试库专属的存储构建引擎 (Read/Write)"""
    def __init__(self):
        self.host = _required_env("DORIS_STORAGE_HOST")
        self.port = _int_env("DORIS_STORAGE_PORT", 9030)
        self.user = _required_env("DORIS_STORAGE_USER")
        self.password = _required_env("DORIS_STORAGE_PASSWORD")
        self.db = os.getenv("DORIS_STORAGE_DATABASE", "test")  # 临时数据统一放在 test 库

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
