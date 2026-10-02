"""交付合同回归：临时合成夹具只验证校验器，不作为实际页面验收证据。"""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from init_project import initialize
from validate_project import CHECKS, REQUIRED, validate


class PageContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in REQUIRED:
            self.write(name, 'fixture')
        self.write('tests/sample.py', '# fixture')
        self.write('static/index.html', '<html>fixture</html>')
        self.write('docs/API中文说明.md', '/api/items')
        self.write_json('docs/openapi.json', {'paths': {'/api/items': {'get': {'summary': '读取条目'}}}})
        self.write_json('docs/MCP工具目录.json', {'tools': [{'name': 'list_items'}]})
        self.contract = {
            'status': 'ready', 'project_name': 'fixture', 'delivery_id': str(uuid4()),
            'prototype': {'sha256': 'a' * 64, 'source_modified': False},
            'operations': [{'method': 'GET', 'path': '/api/items', 'python_example': 'examples/api_client.py', 'mcp_tool': 'list_items'}],
            'checks': [], 'limits': [], 'diagrams': {},
        }
        for name in CHECKS:
            evidence = f'verification/{name}.json'
            self.write_json(evidence, {'passed': True})
            self.contract['checks'].append({'name': name, 'status': 'passed', 'evidence': evidence})
        for name, skill in [('architecture', 'D04'), ('erd', 'G02')]:
            page = f'docs/diagrams/{name}.html'
            source = f'src/{name}.py'
            self.write(page, f'<!doctype html><html><body>{name} fixture</body></html>')
            self.write(source, '# actual source fixture')
            self.contract['diagrams'][name] = {
                'skill': skill, 'path': page, 'sha256': self.sha(page),
                'maintenance': 'created', 'change_note': 'synthetic validator fixture',
                'sources': [{'path': source, 'sha256': self.sha(source)}],
            }
        self.refresh_reports()

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')

    def write_json(self, name, obj):
        self.write(name, json.dumps(obj, ensure_ascii=False))

    def sha(self, name):
        return hashlib.sha256((self.root / name).read_bytes()).hexdigest()

    def refresh_reports(self):
        for name, page in self.contract['diagrams'].items():
            self.write_json(f'verification/{name}.json', {
                'passed': True, 'delivery_id': self.contract['delivery_id'],
                'diagram_sha256': page['sha256'], 'sources': page['sources'],
                'source_consistent': True,
            })

    def result(self):
        self.write_json('project-contract.json', self.contract)
        return validate(self.root)

    def test_complete_contract(self):
        self.assertTrue(self.result()['passed'])

    def test_missing_pages(self):
        for name in ['architecture', 'erd']:
            with self.subTest(name=name):
                path = self.root / self.contract['diagrams'][name]['path']
                content = path.read_bytes()
                path.unlink()
                self.assertFalse(self.result()['passed'])
                path.write_bytes(content)

    def test_stale_source_and_page(self):
        for name in ['src/architecture.py', 'docs/diagrams/erd.html']:
            with self.subTest(name=name):
                path = self.root / name
                original = path.read_bytes()
                path.write_bytes(original + b' changed')
                self.assertFalse(self.result()['passed'])
                path.write_bytes(original)

    def test_invalid_page_metadata(self):
        baseline = copy.deepcopy(self.contract)
        for key, value in [('skill', 'G01'), ('maintenance', 'not_run'), ('change_note', ''), ('sources', []), ('path', '../outside.html'), ('path', str(self.root / 'docs/diagrams/architecture.html'))]:
            with self.subTest(key=key, value=value):
                self.contract = copy.deepcopy(baseline)
                self.contract['diagrams']['architecture'][key] = value
                self.assertFalse(self.result()['passed'])

    def test_images_do_not_replace_html(self):
        page = self.contract['diagrams']['architecture']
        self.write('docs/diagrams/architecture.svg', '<svg></svg>')
        page.update(path='docs/diagrams/architecture.svg', sha256=self.sha('docs/diagrams/architecture.svg'))
        self.refresh_reports()
        self.assertFalse(self.result()['passed'])

    def test_two_distinct_pages_required(self):
        erd = self.contract['diagrams']['erd']
        architecture = self.contract['diagrams']['architecture']
        erd.update(path=architecture['path'], sha256=architecture['sha256'])
        self.refresh_reports()
        self.assertFalse(self.result()['passed'])

    def test_stale_or_failed_evidence(self):
        path = self.root / 'verification/erd.json'
        baseline = json.loads(path.read_text(encoding='utf-8'))
        for key, value in [('passed', False), ('source_consistent', False), ('delivery_id', 'old'), ('diagram_sha256', '0' * 64), ('sources', [])]:
            with self.subTest(key=key):
                self.write_json('verification/erd.json', {**baseline, key: value})
                self.assertFalse(self.result()['passed'])

    def test_reviewed_unchanged_requires_current_report(self):
        self.contract['delivery_id'] = str(uuid4())
        for page in self.contract['diagrams'].values():
            page.update(maintenance='reviewed_unchanged', change_note='本次只修改文案，结构核对一致')
        self.assertFalse(self.result()['passed'])
        self.refresh_reports()
        self.assertTrue(self.result()['passed'])

    def test_page_cannot_be_own_source(self):
        page = self.contract['diagrams']['erd']
        page['sources'] = [{'path': page['path'], 'sha256': page['sha256']}]
        self.refresh_reports()
        self.assertFalse(self.result()['passed'])

    def test_old_contract_rejected(self):
        del self.contract['diagrams']
        self.assertFalse(self.result()['passed'])

    def test_init_preserves_prototype_and_creates_draft_pages_contract(self):
        self.write('prototype.html', '<html><title>原型</title></html>')
        source = self.root / 'prototype.html'
        before = source.read_bytes()
        first = initialize(source, '试验', self.root / 'first')
        second = initialize(source, '试验', self.root / 'second')
        self.assertEqual(source.read_bytes(), before)
        self.assertNotEqual(first['delivery_id'], second['delivery_id'])
        self.assertEqual(first['status'], 'draft')
        self.assertEqual(set(first['diagrams']), {'architecture', 'erd'})
        self.assertTrue(all(p['maintenance'] == 'not_run' for p in first['diagrams'].values()))
        self.assertTrue((self.root / 'first/docs/diagrams').is_dir())
        self.assertFalse(validate(self.root / 'first')['passed'])


if __name__ == '__main__':
    unittest.main()
