"""合成Docker验收夹具；不是业务应用、不是生产部署模板。"""
import os
from contextlib import asynccontextmanager
from pathlib import Path
import httpx
import pymysql
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from mcp.server.fastmcp import FastMCP

TOKEN = os.environ['PROBE_TOKEN']
MODE = os.getenv('MCP_MODE', 'embedded')
ROOT = Path('/app')
DATA = Path('/data')
mcp = FastMCP('h02-docker-probe', stateless_http=True, json_response=True)


def connection():
    return pymysql.connect(host=os.getenv('DB_HOST', 'mysql'), user='probe',
                           password=os.environ['DB_PASSWORD'], database='h02test',
                           connect_timeout=2, read_timeout=3, autocommit=True)


@asynccontextmanager
async def lifespan(app):
    async with mcp.session_manager.run():
        yield


app = FastAPI(lifespan=lifespan)


@app.middleware('http')
async def auth(request: Request, call_next):
    if (request.url.path.startswith('/api/') or request.url.path.startswith('/mcp')) and request.headers.get('authorization') != 'Bearer ' + TOKEN:
        return JSONResponse({'error': 'unauthorized'}, status_code=401)
    return await call_next(request)


@app.get('/health')
def health():
    try:
        if MODE == 'embedded':
            with connection() as c:
                with c.cursor() as cur:
                    cur.execute('SELECT COUNT(*) FROM items')
                    cur.fetchone()
        return {'ok': True, 'version': os.getenv('RELEASE', 'v1')}
    except pymysql.MySQLError:
        return JSONResponse({'ok': False, 'reason': 'database_unavailable'}, status_code=503)


@app.get('/api/items')
def items():
    with connection() as c:
        with c.cursor() as cur:
            cur.execute('SELECT id,name FROM items ORDER BY id')
            rows = cur.fetchall()
    return {'items': [{'id': r[0], 'name': r[1]} for r in rows], 'version': os.getenv('RELEASE', 'v1')}


@app.post('/api/items')
async def create_item(request: Request):
    data = await request.json()
    with connection() as c:
        with c.cursor() as cur:
            cur.execute('INSERT INTO items(id,name) VALUES(%s,%s) ON DUPLICATE KEY UPDATE id=id', (data['id'], data['name']))
    return {'id': data['id']}


@app.put('/api/config')
async def config_write(request: Request):
    DATA.joinpath('setting.txt').write_text((await request.json())['value'], encoding='utf-8')
    return {'saved': True}


@app.get('/api/config')
def config_read():
    return {'value': DATA.joinpath('setting.txt').read_text(encoding='utf-8')}


async def api(method, path, body=None):
    transport = httpx.ASGITransport(app=app) if MODE == 'embedded' else None
    base = 'http://localhost' if transport else os.environ['API_BASE_URL']
    async with httpx.AsyncClient(transport=transport, base_url=base, timeout=10) as client:
        response = await client.request(method, path, json=body, headers={'Authorization': 'Bearer '+TOKEN})
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def list_items() -> dict:
    """读取隔离验收条目。"""
    return await api('GET', '/api/items')


@mcp.tool()
async def create_item_tool(identifier: str, name: str) -> dict:
    """创建合成验收条目；同identifier重复调用不重复插入。"""
    return await api('POST', '/api/items', {'id': identifier, 'name': name})


app.mount('/diagrams', StaticFiles(directory=ROOT/'diagrams'), name='diagrams')
app.mount('/', mcp.streamable_http_app())
