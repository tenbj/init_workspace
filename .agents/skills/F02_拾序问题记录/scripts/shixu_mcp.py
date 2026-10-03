"""受限 MCP 客户端；写入使用已落盘的原请求，成功后回读。"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

READ = {'get_system_status', 'list_issues', 'get_issue'}
WRITE = {'create_issue', 'update_issue'}


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


def validate(tool, arguments):
    if not isinstance(arguments, dict):
        raise ValueError('arguments 必须是 JSON 对象')
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
        allowed = {'request_id', 'expected_version', 'actor', 'title', 'description', 'priority', 'tag'}
        if set(body) - allowed:
            raise ValueError('仅允许问题内容字段，不允许状态或删除操作')


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
        health = await call('get_system_status', {})
        if health.get('status') != 'ok':
            raise RuntimeError('服务未就绪')
        result = health if tool == 'get_system_status' else await call(tool, arguments)
        if tool not in WRITE:
            return result
        # 写入已提交后回读失败也不能创建新的请求编号；保留原请求供重放。
        identifier = result['resource']['id']
        try:
            readback = await call('get_issue', {'issue_id': identifier})
            for field in ('title', 'description', 'tag', 'priority'):
                if field in arguments['body'] and readback['item'][field] != arguments['body'][field]:
                    raise RuntimeError('回读字段不同，可能有后续并发修改：' + field)
        except Exception as exc:
            raise RuntimeError('写入已返回成功，但回读未确认；沿用原请求重试或读取问题 ' + identifier + '；' + str(exc)) from exc
        return {'confirmed': True, 'request_id': arguments['body']['request_id'],
                'revision': readback['revision'], 'item': readback['item']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--application')
    parser.add_argument('--url', default='http://127.0.0.1:8765')
    parser.add_argument('--tool', required=True, choices=sorted(READ | WRITE))
    parser.add_argument('--input', help='MCP arguments JSON文件；写工具必填，重试复用原文件')
    parser.add_argument('--output', help='可选结果JSON；使用子项目03_代码程序下任务目录')
    args = parser.parse_args()
    try:
        if args.tool in WRITE and not args.input:
            raise ValueError('写入必须提供 --input，先落盘请求再执行')
        values = json.loads(Path(args.input).read_text(encoding='utf-8-sig')) if args.input else {}
        validate(args.tool, values)
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
