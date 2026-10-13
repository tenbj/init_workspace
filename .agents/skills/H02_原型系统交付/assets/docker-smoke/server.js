// 合成Node/MySQL夹具；用于验证独立MCP容器，不是生产应用模板。
const http=require('node:http'), fs=require('node:fs/promises');
const mysql=require('mysql2/promise');
const token=process.env.PROBE_TOKEN;
const pool=mysql.createPool({host:process.env.DB_HOST||'mysql',user:'probe',password:process.env.DB_PASSWORD,database:'h02test',connectTimeout:2000});
const server=http.createServer(async(req,res)=>{
 const send=(status,obj)=>{res.writeHead(status,{'Content-Type':'application/json'});res.end(JSON.stringify(obj));};
 try {
  if(req.url==='/health'){await pool.query('SELECT COUNT(*) FROM items');return send(200,{ok:true,version:process.env.RELEASE});}
  if(['/diagrams/architecture.html','/diagrams/erd.html'].includes(req.url)){res.writeHead(200,{'Content-Type':'text/html'});return res.end(await fs.readFile('/app'+req.url));}
  if(req.headers.authorization!=='Bearer '+token)return send(401,{error:'unauthorized'});
  let raw='';for await (const chunk of req)raw+=chunk;const body=raw?JSON.parse(raw):{};
  if(req.url==='/api/items'&&req.method==='GET'){const [items]=await pool.query('SELECT id,name FROM items ORDER BY id');return send(200,{items,version:process.env.RELEASE});}
  if(req.url==='/api/items'&&req.method==='POST'){await pool.execute('INSERT INTO items(id,name) VALUES(?,?) ON DUPLICATE KEY UPDATE id=id',[body.id,body.name]);return send(200,{id:body.id});}
  if(req.url==='/api/config'&&req.method==='PUT'){await fs.writeFile('/data/setting.txt',body.value);return send(200,{saved:true});}
  if(req.url==='/api/config'&&req.method==='GET')return send(200,{value:await fs.readFile('/data/setting.txt','utf8')});
  send(404,{error:'not_found'});
 }catch(e){send(503,{error:'dependency_unavailable'});}
});
server.listen(8080,'0.0.0.0');
process.on('SIGTERM',()=>server.close(()=>pool.end().then(()=>process.exit(0))));
