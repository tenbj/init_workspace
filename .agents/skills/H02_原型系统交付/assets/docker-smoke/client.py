"""在测试镜像内用真实MCP SDK完成握手、发现、写入和回读。"""
import asyncio
import json
import os
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main():
    headers={'Authorization':'Bearer '+os.environ['PROBE_TOKEN']}
    async with streamablehttp_client(os.environ['PROBE_MCP_URL'], headers=headers) as (read,write,_):
        async with ClientSession(read,write) as session:
            await session.initialize()
            names={t.name for t in (await session.list_tools()).tools}
            assert names=={'list_items','create_item_tool'},names
            result=await session.call_tool('create_item_tool',{'identifier':'mcp-probe','name':'sdk-created'})
            assert not result.isError
            result=await session.call_tool('list_items',{})
            assert not result.isError
            data=json.loads(next(c.text for c in result.content if c.type=='text'))
            assert any(r['id']=='mcp-probe' for r in data['items'])
            print(json.dumps({'passed':True,'tools':sorted(names),'read_back':True}))


asyncio.run(main())
