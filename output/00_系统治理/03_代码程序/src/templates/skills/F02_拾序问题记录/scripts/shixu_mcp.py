"""受限 MCP 客户端；写入使用已落盘的原请求，成功后回读。"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

READ = {'get_system_status', 'list_identities', 'list_issues', 'get_issue'}
WRITE = {'create_identity', 'create_issue', 'update_issue'}
SNAPSHOT = ('createdByActorId', 'initiatedByPersonId', 'creatorName',
            'createdVia', 'createdAt', 'modelInfo')


def locate(application=None):
    if application:
        root = Path(application).resolve()
        if not (root / 'mcp_server.py').is_file():
            raise ValueError('application 下缺少 mcp_server.py')
        return root
    workspace = Path(__file__).resolve().parents[4]
    matches = list((workspace / 'output').glob('*/03_代码程序/*/application/mcp_server.py'))
    if len(matches) != 1:
        raise ValueError('应用定位不唯一，请传 --application；不猜测目标')
    return matches[0].parent


def validate(tool, arguments, legacy_retry=False):
    if tool not in READ | WRITE:
        raise ValueError('不支持的工具')
    if not isinstance(arguments, dict):
        raise ValueError('arguments 必须是 JSON 对象')
    if legacy_retry and tool != 'create_issue':
        raise ValueError('--legacy-retry 仅用于缺少 creation 的旧 create_issue 原请求')
    if tool in WRITE:
        body = arguments.get('body', {})
        if not isinstance(body, dict):
            raise ValueError('body 必须是对象')
        if not isinstance(body.get('request_id'), str) or len(body['request_id']) < 8:
            raise ValueError('写入必须携带持久化的 request_id')
        version = body.get('expected_version')
        if type(version) is not int or version < 0:
            raise ValueError('写入必须携带读取到的 expected_version')
        if tool == 'create_issue' and not str(body.get('tag', '')).strip():
            raise ValueError('创建前须由AI定义开放分类 tag')
        allowed = {'request_id', 'expected_version', 'actor'}
        if tool == 'create_identity':
            allowed |= {'name', 'kind', 'via', 'modelName', 'modelProvider'}
        else:
            allowed |= {'title', 'description', 'priority', 'tag'}
        if tool == 'create_issue':
            allowed.add('creation')
            creation = body.get('creation')
            if legacy_retry:
                if creation is not None:
                    raise ValueError('带 creation 的请求不需要 --legacy-retry')
            else:
                if not isinstance(creation, dict):
                    raise ValueError('新问题必须显式提供 creation；仅旧原请求重试可用 --legacy-retry')
                if set(creation) - {'identityId', 'initiatedByPersonId', 'modelInfo'}:
                    raise ValueError('creation 含不支持的字段')
                identity = creation.get('identityId')
                if not isinstance(identity, str) or not identity.strip():
                    raise ValueError('creation.identityId 必须是实际 AI 身份 ID')
                initiator = creation.get('initiatedByPersonId')
                if initiator is not None and (not isinstance(initiator, str) or not initiator.strip()):
                    raise ValueError('发起者须为已有人员 ID；未提供时用 null 或省略')
                model = creation.get('modelInfo')
                if not isinstance(model, dict) or set(model) - {'name', 'provider'}:
                    raise ValueError('逐次显式传 modelInfo；无法确认模型时传空对象，不继承档案默认值')
                if any(not isinstance(value, str) for value in model.values()):
                    raise ValueError('模型名称和提供方必须是字符串')
        if set(body) - allowed:
            raise ValueError('不允许状态、删除操作或修改已有创建来源')


async def execute(call, tool, arguments):
    health = await call('get_system_status', {})
    if health.get('status') != 'ok':
        raise RuntimeError('服务未就绪')
    result = health if tool == 'get_system_status' else await call(tool, arguments)
    if tool not in WRITE:
        return result
    identifier = result['resource']['id']
    try:
        if tool == 'create_identity':
            readback = await call('list_identities', {})
            item = next(item for item in readback['items'] if item['id'] == identifier)
            fields = ('name', 'kind', 'via', 'modelName', 'modelProvider')
        else:
            readback = await call('get_issue', {'issue_id': identifier})
            item = readback['item']
            fields = ('title', 'description', 'tag', 'priority', 'status') + SNAPSHOT
        # 对照本次写入响应快照，而非可被重命名或切换模型的当前身份档案。
        for field in fields:
            if field not in item or field not in result['resource'] or item[field] != result['resource'][field]:
                raise RuntimeError('回读字段不同或缺失，可能有后续并发修改：' + field)
            if field in arguments['body']:
                expected = arguments['body'][field]
                if isinstance(expected, str):
                    expected = expected.strip()
                if item[field] != expected:
                    raise RuntimeError('回读与请求字段不同：' + field)
        if item['id'] != identifier:
            raise RuntimeError('回读编号不同')
        creation = arguments['body'].get('creation')
        if tool == 'create_issue' and creation:
            expected_model = {key: creation['modelInfo'].get(key, '').strip() for key in ('name', 'provider')}
            if (item['createdByActorId'] != creation['identityId']
                    or item['initiatedByPersonId'] != creation.get('initiatedByPersonId')
                    or item['modelInfo'] != expected_model
                    or item['createdVia'] not in {'claude_code', 'workbuddy', 'codex', 'deepseek_harness'}
                    or not item['createdAt']):
                raise RuntimeError('创建身份、发起人、AI 工具、模型或创建时间未按请求保存')
    except Exception as exc:
        raise RuntimeError('写入已返回成功，但回读未确认；沿用原请求重试或读取资源 '
                           + identifier + '；' + str(exc)) from exc
    return {'confirmed': True, 'request_id': arguments['body']['request_id'],
            'revision': readback['revision'], 'item': item}


async def run(application, url, tool, arguments):
    from mcp import Client, StdioServerParameters
    params = StdioServerParameters(command=sys.executable,
        args=[str(application / 'mcp_server.py')],
        env=dict(os.environ, SHIXU_API_URL=url, PYTHONIOENCODING='utf-8'))
    async with Client(params) as client:
        async def call(name, values):
            response = await client.call_tool(name, values)
            if response.is_error:
                raise RuntimeError(str(response.content))
            return response.structured_content or json.loads(response.content[0].text)
        return await execute(call, tool, arguments)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--application')
    parser.add_argument('--url', default='http://127.0.0.1:8765')
    parser.add_argument('--tool', required=True, choices=sorted(READ | WRITE))
    parser.add_argument('--input', help='MCP arguments JSON文件；写工具必填，重试复用原文件')
    parser.add_argument('--output', help='可选结果JSON；使用子项目03_代码程序下任务目录')
    parser.add_argument('--legacy-retry', action='store_true', help='仅重放升级前已发送且没有 creation 的原请求；禁止用于新记录')
    args = parser.parse_args()
    try:
        if args.tool in WRITE and not args.input:
            raise ValueError('写入必须提供 --input，先落盘请求再执行')
        values = json.loads(Path(args.input).read_text(encoding='utf-8-sig')) if args.input else {}
        validate(args.tool, values, args.legacy_retry)
        result = asyncio.run(run(locate(args.application), args.url, args.tool, values))
        rendered = json.dumps(result, ensure_ascii=False, indent=2)
        if args.output:
            Path(args.output).write_text(rendered, encoding='utf-8')
        print(rendered)
        return 0
    except Exception as exc:
        print(json.dumps({'confirmed': False, 'error': str(exc),
            'retry': '结果未知时复用原input和request_id；409重读评估，422修正参数'}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
