"""Offline guard regression: never initializes credentials or connects to a DB."""
import unittest
from doris_query_client import DorisQueryClient


class ReadOnlyGuardTests(unittest.TestCase):
    def setUp(self):
        self.client = object.__new__(DorisQueryClient)

    def test_scalar_replace_in_read_queries(self):
        for sql in [
            "SELECT REPLACE(name, 'a', 'b') FROM t",
            "WITH c AS (SELECT replace (name, '-', '') AS n FROM t) SELECT n FROM c",
            "SELECT REPLACE(REPLACE(name, 'a', 'b'), 'c', 'd') FROM t",
            "EXPLAIN SELECT REPLACE(name, 'a', 'b') FROM t",
        ]:
            with self.subTest(sql=sql):
                self.client._guard(sql)

    def test_writes_still_blocked(self):
        for sql in [
            "REPLACE INTO t VALUES (1)",
            "replace t (id) values (1)",
            "REPLACE /* comment */ INTO t SELECT 1",
            "SELECT REPLACE(name,'a','b') FROM t; DELETE FROM t",
            "INSERT INTO t SELECT REPLACE(name,'a','b') FROM s",
            "UPDATE t SET name=REPLACE(name,'a','b')",
            "DELETE FROM t", "DROP TABLE t", "ALTER TABLE t ADD x INT",
            "TRUNCATE TABLE t", "CREATE TABLE t (id INT)",
            "GRANT SELECT ON t TO u", "REVOKE SELECT ON t FROM u",
            "LOAD DATA INFILE 'file' INTO TABLE t",
        ]:
            with self.subTest(sql=sql), self.assertRaises(ValueError):
                self.client._guard(sql)


if __name__ == '__main__':
    unittest.main()
