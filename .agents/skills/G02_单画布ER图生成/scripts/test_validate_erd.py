#!/usr/bin/env python3
"""Unit tests for validate_erd helpers; browser integration is tested by the CLI."""

import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("validate_erd.py")
SPEC = importlib.util.spec_from_file_location("validate_erd", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class ValidatorTests(unittest.TestCase):
    def test_static_forbidden_features(self):
        source = '<script src="https://cdn.example/a.js"></script><script>localStorage.x=1</script>'
        errors = MODULE.static_errors(source)
        self.assertIn("存在外部资源 URL", errors)
        self.assertIn("存在持久化字段状态", errors)

    def test_rendered_contract_passes(self):
        attrs = {name: "pass" for name in MODULE.PASS_ATTRS}
        attrs.update({name: "0" for name in MODULE.ZERO_ATTRS})
        attrs.update({"data-tables": "12", "data-relations": "15"})
        self.assertEqual([], MODULE.rendered_errors(attrs, 12, 15))

    def test_missing_contract_fails(self):
        errors = MODULE.rendered_errors({}, 2, 1)
        self.assertGreaterEqual(len(errors), len(MODULE.PASS_ATTRS) + len(MODULE.ZERO_ATTRS) + 2)


if __name__ == "__main__":
    unittest.main()
