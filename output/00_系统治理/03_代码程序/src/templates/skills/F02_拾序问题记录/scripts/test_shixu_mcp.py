"""F02来源、幂等与回读验证；仅临时SQLite、随机端口、真实stdio MCP。"""
import asyncio
import copy
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from uuid import uuid4

import httpx
import shixu_mcp as subject


def request(**values):
    return {'body': dict(request_id=str(uuid4()), expected_version=0,
                         title='测试问题', tag='集成验证', actor='Codex', **values)}


class Guards(unittest.TestCase):
    def test_new_issue_requires_source(self):
        with self.assertRaisesRegex(ValueError, 'creation'):
            subject.validate('create_issue', request())

    def test_model_must_be_explicit_but_may_be_unknown(self):
        for model in (None, 'GPT', {'name': 1}, {'version': 'x'}):
            with self.subTest(model=model), self.assertRaises(ValueError):
                subject.validate('create_issue', request(creation={'identityId': 'ai', 'modelInfo': model}))
        subject.validate('create_issue', request(creation={'identityId': 'ai', 'modelInfo': {}}))
        subject.validate('create_issue', request(creation={'identityId': 'ai', 'modelInfo': {'name': 'GPT-6.1 Sol'}}))

    def test_legacy_retry_is_explicit_and_does_not_mutate(self):
        args = request()
        original = copy.deepcopy(args)
        subject.validate('create_issue', args, legacy_retry=True)
        self.assertEqual(args, original)
        with self.assertRaises(ValueError):
            subject.validate('update_issue', args, legacy_retry=True)
        with self.assertRaises(ValueError):
            subject.validate('create_issue', request(creation={'identityId': 'ai', 'modelInfo': {}}), True)

    def test_cannot_rewrite_source_or_transition(self):
        for field in ('creation', *subject.SNAPSHOT, 'status', 'action'):
            with self.subTest(field=field), self.assertRaises(ValueError):
                subject.validate('update_issue', request(**{field: 'forbidden'}))
        for tool in ('update_identity', 'delete_issue', 'transition_issue', 'create_task'):
            with self.subTest(tool=tool), self.assertRaises(ValueError):
                subject.validate(tool, {})

    def test_all_snapshot_fields_and_status_checked(self):
        item = dict(id='issue-id', title='测试问题', description='', tag='集成验证', priority='中',
                    status='待梳理', createdByActorId='ai', initiatedByPersonId='person',
                    creatorName='Elias', createdVia='codex', createdAt='2026-10-03T00:00:00+00:00',
                    modelInfo={'name': 'GPT-6.1 Sol', 'provider': 'OpenAI'})
        args = request(creation={'identityId': 'ai', 'initiatedByPersonId': 'person',
                                 'modelInfo': item['modelInfo']})
        for field in (*subject.SNAPSHOT, 'status', 'id'):
            async def call(tool, values):
                if tool == 'get_system_status':
                    return {'status': 'ok'}
                if tool == 'create_issue':
                    return {'resource': item, 'revision': 1}
                changed = dict(item, **{field: 'changed'})
                return {'item': changed, 'revision': 2}
            with self.subTest(field=field), self.assertRaisesRegex(RuntimeError, '回读未确认'):
                asyncio.run(subject.execute(call, 'create_issue', args))

    def test_success_response_cannot_hide_wrong_request_model(self):
        item = dict(id='issue-id', title='测试问题', description='', tag='集成验证', priority='中',
                    status='待梳理', createdByActorId='ai', initiatedByPersonId=None,
                    creatorName='Codex', createdVia='codex', createdAt='timestamp',
                    modelInfo={'name': 'stale-default', 'provider': ''})
        async def call(tool, values):
            if tool == 'get_system_status':
                return {'status': 'ok'}
            return {'resource': item, 'item': item, 'revision': 1}
        with self.assertRaisesRegex(RuntimeError, '回读未确认'):
            asyncio.run(subject.execute(call, 'create_issue', request(creation={'identityId': 'ai', 'modelInfo': {}})))


class RealMCP(unittest.TestCase):
    def test_full_source_lifecycle(self):
        app = subject.locate()
        with tempfile.TemporaryDirectory(prefix='f02-source-') as directory:
            root = Path(directory)
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            url = f'http://127.0.0.1:{port}'
            env = dict(os.environ, SHIXU_BACKEND='sqlite', SHIXU_DB=str(root/'test.sqlite3'),
                       PYTHONIOENCODING='utf-8')
            flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app',
                                        '--host', '127.0.0.1', '--port', str(port)], cwd=app, env=env,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
            try:
                with httpx.Client(base_url=url, trust_env=False, timeout=10) as http:
                    for _ in range(100):
                        self.assertIsNone(process.poll(), '临时验证服务提前退出')
                        try:
                            health = http.get('/api/health').raise_for_status().json()
                            break
                        except httpx.HTTPError:
                            time.sleep(.1)
                    else:
                        self.fail('临时服务未启动')
                    self.assertEqual(health['backend'], 'sqlite-test')

                    def body(**values):
                        revision = http.get('/api/workspace').raise_for_status().json()['revision']
                        return dict(request_id=str(uuid4()), expected_version=revision, actor='Codex', **values)

                    def cli(tool, args=None, legacy=False, path=None):
                        command = [sys.executable, str(Path(subject.__file__).resolve()),
                                   '--application', str(app), '--url', url, '--tool', tool]
                        if args is not None:
                            path = path or root / (str(uuid4()) + '.json')
                            if not path.exists():
                                path.write_text(json.dumps(args, ensure_ascii=False), encoding='utf-8')
                            before = path.read_bytes()
                            command += ['--input', str(path)]
                        if legacy:
                            command += ['--legacy-retry']
                        completed = subprocess.run(command, env=env, capture_output=True, text=True,
                                                   encoding='utf-8', timeout=40, creationflags=flags)
                        self.assertEqual(completed.returncode, 0, completed.stderr)
                        if args is not None:
                            self.assertEqual(path.read_bytes(), before, '原请求被改变')
                        return json.loads(completed.stdout)

                    self.assertEqual(cli('list_identities')['items'], [])
                    person = cli('create_identity', {'body': body(name='Elias', kind='person', via='manual')})['item']
                    ai = cli('create_identity', {'body': body(name='Codex', kind='agent', via='codex',
                                                             modelName='stale-default', modelProvider='old')})['item']
                    args = {'body': body(title='Elias委托录入', tag='测试', creation={
                        'identityId': ai['id'], 'initiatedByPersonId': person['id'],
                        'modelInfo': {'name': 'GPT-6.1 Sol', 'provider': 'OpenAI'}})}
                    original_file = root/'original.json'
                    first = cli('create_issue', args, path=original_file)
                    item = first['item']
                    self.assertTrue(first['confirmed'])
                    self.assertEqual(item['creatorName'], 'Elias')
                    self.assertEqual(item['createdVia'], 'codex')
                    self.assertEqual(item['modelInfo']['name'], 'GPT-6.1 Sol')
                    http.patch('/api/identities/' + person['id'], json=body(name='Renamed')).raise_for_status()
                    http.patch('/api/identities/' + ai['id'], json=body(modelName='changed-default')).raise_for_status()
                    replay = cli('create_issue', args, path=original_file)
                    self.assertEqual(replay['item'], item, '档案修改不得改变旧请求快照')
                    changed = cli('update_issue', {'issue_id': item['id'], 'body': body(description='补充背景')})['item']
                    self.assertEqual({k: changed[k] for k in subject.SNAPSHOT}, {k: item[k] for k in subject.SNAPSHOT})
                    unknown = cli('create_issue', {'body': body(title='未知模型但工具已知', tag='测试',
                                  creation={'identityId': ai['id'], 'modelInfo': {}})})['item']
                    self.assertEqual(unknown['modelInfo'], {'name': '', 'provider': ''})
                    self.assertEqual(unknown['creatorName'], 'Codex')
                    self.assertIsNone(unknown['initiatedByPersonId'])
                    # 其他三种工具使用同一接口，模型不从工具名猜测。
                    for via in ('claude_code', 'workbuddy', 'deepseek_harness'):
                        agent = cli('create_identity', {'body': body(name=via, kind='agent', via=via)})['item']
                        record = cli('create_issue', {'body': body(title=via, tag='测试',
                                     creation={'identityId': agent['id'], 'modelInfo': {'name': 'explicit-test-model'}})})['item']
                        self.assertEqual(record['createdVia'], via)
                        self.assertEqual(record['modelInfo']['name'], 'explicit-test-model')
                    # 用旧API形状模拟升级前已提交请求，再由新版技能按原文恢复。
                    legacy = {'body': body(title='旧请求', tag='测试')}
                    original = http.post('/api/issues', json=legacy['body']).raise_for_status().json()['resource']
                    recovered = cli('create_issue', legacy, legacy=True)['item']
                    self.assertEqual(original, recovered)
                    self.assertEqual(recovered['createdVia'], 'unknown')
                    all_issues = cli('list_issues')['items']
                    self.assertEqual(len(all_issues), 6, '幂等重试不应新增记录')
                    self.assertEqual(cli('get_issue', {'issue_id': item['id']})['item'], changed)
            finally:
                if process.poll() is None:
                    if os.name == 'nt':
                        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                       check=True, capture_output=True, creationflags=flags)
                    else:
                        process.terminate()
                    process.wait(timeout=10)


if __name__ == '__main__':
    unittest.main(verbosity=2)
