"""显式运行隔离Docker合成演练：Python内置MCP、Node+独立MCP、真实MySQL。
只操作本次随机项目名的资源；不读真实系统配置。需要联网拉取依赖。
"""
from __future__ import annotations
import argparse
import hashlib
import gzip
import io
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import subprocess
import tarfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from uuid import uuid4
from docker_contract import STAGES, snapshot, validate_docker
from docker_preflight import probe


def now():
    return datetime.now(timezone.utc).isoformat()


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def dump(path, data):
    write(path, json.dumps(data, ensure_ascii=False, indent=2))


def bounded_run(args, *, timeout, **kwargs):
    stdin=kwargs.pop('input',None)
    kwargs.pop('capture_output',None)
    process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               start_new_session=os.name!='nt', **kwargs)
    try:
        out,err=process.communicate(stdin,timeout=timeout)
    except BaseException as original:
        # 取消与超时均先回收本次命令树，避免finally清理后仍有后台up继续启动。
        try:
            if os.name=='nt':
                killed=subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],
                                      capture_output=True,timeout=20,
                                      creationflags=subprocess.CREATE_NO_WINDOW)
                if killed.returncode and process.poll() is None:
                    raise RuntimeError('owned_command_tree_termination_failed')
            else:
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
            out,err=process.communicate(timeout=20)
            for pipe in (process.stdin,process.stdout,process.stderr):
                if pipe is not None:pipe.close()
        except BaseException as cleanup:
            original.add_note('owned_command_cleanup_failed:'+type(cleanup).__name__)
            raise original
        if not isinstance(original,subprocess.TimeoutExpired):raise
        return subprocess.CompletedProcess(args,124,out,err+b'\ncommand_timeout')
    for pipe in (process.stdin,process.stdout,process.stderr):
        if pipe is not None:pipe.close()
    return subprocess.CompletedProcess(args,process.returncode,out,err)


def scan_archive(archive, needles):
    checked=0
    with tarfile.open(archive) as outer:
        for member in outer:
            if not member.isfile():continue
            f=outer.extractfile(member)
            magic=f.read(4);f.seek(0)
            # containerd导出的OCI层可能gzip压缩，必须解压扫描，不能只扫压缩字节。
            if magic==b'\x28\xb5\x2f\xfd':raise ValueError('zstd_layer_requires_supported_decoder')
            stream=gzip.GzipFile(fileobj=f) if magic[:2]==b'\x1f\x8b' else f
            tail=b''
            while True:
                chunk=stream.read(1024*1024)
                if not chunk:break
                block=tail+chunk
                if any(n in block for n in needles):raise ValueError('secret_in_image_layer_or_metadata')
                tail=block[-max(map(len,needles)):];checked+=len(chunk)
    return checked


class Trial:
    def __init__(self, root, mode, images, reuse_cache=False, startup_timeout=900):
        self.root, self.mode, self.base_images = root.resolve(), mode, images
        self.project = 'h02test-' + uuid4().hex[:12]
        self.token, self.password, self.canary = (secrets.token_hex(24) for _ in range(3))
        self.env = dict(os.environ, H02_RELEASE='v1')
        self.records = []
        self.report = dict(passed=False, environment='isolated', delivery_id=str(uuid4()),
                           run_id=str(uuid4()), started_at=now(), compose_project=self.project,
                           mcp_mode=mode, checks=self.records, images=[])
        self.tags = []
        self.reuse_cache = reuse_cache
        self.startup_timeout = startup_timeout
        self.report['startup_timeout_seconds'] = startup_timeout

    def run(self, args, *, timeout=180, stdin=None, check=True, log=True):
        p = bounded_run(args, cwd=self.root, env=self.env, input=stdin,
                           capture_output=True, timeout=timeout)
        if log:
            output=(p.stdout+p.stderr).decode('utf-8', errors='replace')
            for secret in (self.token, self.password, self.canary):
                output=output.replace(secret, '[redacted]')
            with (self.root/'private/commands.log').open('a', encoding='utf-8') as f:
                f.write('COMMAND '+json.dumps(args, ensure_ascii=False)+'\n'+output+'\n')
        if check and p.returncode:
            raise RuntimeError('command_failed:'+str(p.returncode)+':'+args[0]+(' '+args[1] if len(args)>1 else ''))
        return p

    def compose(self, *args, **kwargs):
        return self.run(['docker','compose','-p',self.project,'--env-file','.env','-f','compose.yaml',*args], **kwargs)

    def mark(self, name, **observations):
        self.records.append(dict(name=name,status='passed',observations=observations))
        print(self.mode+': '+name+' passed', flush=True)

    def prepare(self):
        self.root.mkdir(parents=True)
        (self.root/'private').mkdir()
        assets=Path(__file__).resolve().parents[1]/'assets/docker-smoke'
        (self.root/'src').mkdir()
        for name in ['server.py','server.js','client.py']:
            shutil.copyfile(assets/name,self.root/'src'/name)
        shutil.copyfile(assets/'requirements.txt',self.root/'requirements.txt')
        shutil.copyfile(assets/'schema.sql',self.root/'schema.sql')
        for name in ['architecture','erd']:
            write(self.root/f'diagrams/{name}.html','<!doctype html><html lang="zh"><meta charset="utf-8"><title>'+name+'</title><body><h1>H02 synthetic '+name+'</h1><button onclick="this.textContent=\'checked\'">check</button></body></html>')
        write(self.root/'package.json',json.dumps({'name':'h02-synthetic-probe','version':'1.0.0','private':True,'dependencies':{'mysql2':'3.14.3'}}))
        write(self.root/'.env',f'PROBE_TOKEN={self.token}\nMYSQL_PASSWORD={self.password}\nMYSQL_ROOT_PASSWORD={self.canary}\n')
        write(self.root/'.dockerignore','.env\nprivate/\nverification/\nproject-contract.json\n*.tar\n__pycache__/\n')
        common='WORKDIR /app\nCOPY src/ /app/\nCOPY diagrams/ /app/diagrams/\nRUN mkdir -p /data && chown 10001:10001 /data\nARG RELEASE=v1\nENV RELEASE=$RELEASE\nUSER 10001:10001\n'
        write(self.root/'Dockerfile.python',f'FROM {self.base_images["python"]}\nWORKDIR /app\nCOPY requirements.txt /app/\nRUN pip install --no-cache-dir -r requirements.txt && pip check\n'+common+'RUN PROBE_TOKEN=build-import-probe python -c "import server; print(\'application-import-ok\')"\nCMD ["python","-m","uvicorn","server:app","--host","0.0.0.0","--port","8080"]\n')
        write(self.root/'Dockerfile.node',f'FROM {self.base_images["node"]}\nWORKDIR /app\nCOPY package.json /app/\nRUN npm install --omit=dev --ignore-scripts --no-audit --no-fund\n'+common+'CMD ["node","server.js"]\n')
        write(self.root/'Dockerfile.mysql',f'FROM {self.base_images["mysql"]}\nCOPY schema.sql /docker-entrypoint-initdb.d/01-schema.sql\n')
        db=dict(image=self.project+'-mysql:schema',build={'context':'.','dockerfile':'Dockerfile.mysql'},environment={'MYSQL_DATABASE':'h02test','MYSQL_USER':'probe','MYSQL_PASSWORD':'${MYSQL_PASSWORD:?}','MYSQL_ROOT_PASSWORD':'${MYSQL_ROOT_PASSWORD:?}'},
                volumes=['db_data:/var/lib/mysql'],mem_limit='512m',command=['--performance-schema=OFF','--innodb-buffer-pool-size=32M','--max-connections=20'],
                healthcheck={'test':['CMD-SHELL','MYSQL_PWD="$$MYSQL_PASSWORD" mysql -h127.0.0.1 -u"$$MYSQL_USER" "$$MYSQL_DATABASE" -e "SELECT 1 FROM items LIMIT 0"'], 'interval':'3s','timeout':'5s','retries':self.startup_timeout//3+10,'start_period':'30s'})
        pyhealth={'test':['CMD','python','-c',"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health',timeout=2)"], 'interval':'2s','timeout':'3s','retries':40}
        nodehealth={'test':['CMD','node','-e',"fetch('http://127.0.0.1:8080/health').then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"], 'interval':'2s','timeout':'3s','retries':40}
        kind='python' if self.mode=='embedded' else 'node'
        app=dict(image=self.project+'-'+kind+':${H02_RELEASE:-v1}',build={'context':'.','dockerfile':'Dockerfile.'+kind,'args':{'RELEASE':'${H02_RELEASE:-v1}'}},
                 ports=['127.0.0.1::8080'],environment={'DB_HOST':'mysql','DB_PASSWORD':'${MYSQL_PASSWORD:?}','PROBE_TOKEN':'${PROBE_TOKEN:?}','MCP_MODE':'embedded'},
                 depends_on={'mysql':{'condition':'service_healthy'}},volumes=['app_data:/data'],healthcheck=pyhealth if kind=='python' else nodehealth)
        services={'mysql':db,'app':app}
        if self.mode=='separate':
            services['mcp']=dict(image=self.project+'-python:${H02_RELEASE:-v1}', build={'context':'.','dockerfile':'Dockerfile.python','args':{'RELEASE':'${H02_RELEASE:-v1}'}},
                ports=['127.0.0.1::8080'], environment={'MCP_MODE':'separate','API_BASE_URL':'http://app:8080','PROBE_TOKEN':'${PROBE_TOKEN:?}'},
                depends_on={'app':{'condition':'service_healthy'}},healthcheck=pyhealth)
        for service in services.values():
            service.update(restart='no', mem_limit='512m', cpus=0.5)
        dump(self.root/'compose.yaml',{'services':services,'volumes':{'db_data':{},'app_data':{}}})
        write(self.root/'docs/Docker部署.md','合成回归夹具；独立Compose项目、动态回环端口及新MySQL库。不会部署业务系统。')
        self.contract={'delivery_id':self.report['delivery_id'], 'diagrams':{k:{'path':f'diagrams/{k}.html'} for k in ['architecture','erd']},
            'docker':dict(required=True,mcp_mode=self.mode,stateful=True,compose_files=['compose.yaml'],dockerfiles=['Dockerfile.python','Dockerfile.node','Dockerfile.mysql'],
                          ignore_files=['.dockerignore'],guide='docs/Docker部署.md',inputs=['src','diagrams','schema.sql','requirements.txt','package.json','Dockerfile.python','Dockerfile.node','Dockerfile.mysql','.dockerignore','compose.yaml','docs'],
                          services=list(services),evidence='verification/docker-report.json'),
            'checks':[dict(name='docker',status='not_run',evidence='verification/docker-report.json')]}
        self.report['inputs']=snapshot(self.root,self.contract['docker']['inputs'])
        dump(self.root/'project-contract.json',self.contract)
        self.tags=[self.project+'-'+k+':'+v for k in ({kind,'python'}) for v in ['v1','v2']]
        self.tags.append(self.project+'-mysql:schema')

    def address(self, service):
        value=self.compose('port',service,'8080').stdout.decode().strip()
        if not value.startswith('127.0.0.1:'):
            raise RuntimeError('unexpected_port_binding')
        return 'http://'+value

    def http(self, path, *, method='GET', body=None, auth=True, service='app'):
        headers={'Authorization':'Bearer '+(self.token if auth is True else str(auth))} if auth else {}
        if body is not None:headers['Content-Type']='application/json'
        request=urllib.request.Request(self.address(service)+path, data=json.dumps(body).encode() if body is not None else None, method=method, headers=headers)
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(request,timeout=10) as r:return r.status,r.read(),r.headers.get('Content-Type','')
        except urllib.error.HTTPError as e:return e.code,e.read(),e.headers.get('Content-Type','')

    def data(self,path,**kwargs):
        code,body,_=self.http(path,**kwargs)
        if code!=200:raise RuntimeError('HTTP_'+str(code)+':'+path)
        return json.loads(body)

    def assert_data(self):
        items=self.data('/api/items')['items']
        assert {i['id'] for i in items}=={'api-probe','mcp-probe'},items
        assert self.data('/api/config')['value']=='retained-setting'

    def capture_images(self):
        ids=self.compose('ps','-q').stdout.decode().split()
        data=json.loads(self.run(['docker','inspect',*ids],log=False).stdout)
        self.report['images']=[{'service':d['Config']['Labels']['com.docker.compose.service'],'id':d['Image']} for d in data]

    def scan_image(self, tag):
        archive=self.root/'private/image.tar'
        self.run(['docker','image','save','-o',str(archive),tag],timeout=300)
        needles=[x.encode() for x in [self.token,self.password,self.canary]]
        checked=scan_archive(archive,needles)
        archive.unlink()
        return checked

    def execute(self):
        self.prepare()
        primary=None
        try:
            parsed=json.loads(self.compose('config','--format','json',log=False).stdout)
            assert set(parsed['services'])==set(self.contract['docker']['services'])
            self.mark('compose_config',services=sorted(parsed['services']),secrets_not_logged=True)
            self.compose('build',*([] if self.reuse_cache else ['--no-cache']),timeout=900)
            self.mark('build',base_images=self.base_images,clean_build=not self.reuse_cache)
            self.compose('up','-d','--pull','never','--wait','--wait-timeout',str(self.startup_timeout),timeout=self.startup_timeout+120)
            assert self.data('/health',auth=False)['version']=='v1'
            self.mark('startup',healthy=True,release='v1')
            for _ in range(2):self.data('/api/items',method='POST',body={'id':'api-probe','name':'synthetic'})
            assert len(self.data('/api/items')['items'])==1
            self.data('/api/config',method='PUT',body={'value':'retained-setting'})
            self.mark('api',write_read=True,duplicate_request_retained_one=True,nonroot_volume_write=True)
            svc='app' if self.mode=='embedded' else 'mcp'
            result=json.loads(self.compose('exec','-T','-e','PROBE_MCP_URL=http://127.0.0.1:8080/mcp',svc,'python','client.py').stdout)
            assert result['passed'];self.assert_data()
            self.mark('mcp',sdk=result,transport='streamable-http',mock=False)
            assert self.http('/api/items',auth=False)[0]==401
            assert self.http('/mcp',auth=False,service=svc,method='POST',body={})[0]==401
            assert self.http('/api/items',auth='invalid-test-credential')[0]==401
            assert self.http('/mcp',auth='invalid-test-credential',service=svc,method='POST',body={})[0]==401
            self.mark('auth',unauthenticated_api=401,unauthenticated_mcp=401,invalid_credentials=401,valid_authenticated_sdk=True)
            hashes={}
            for name in ['architecture','erd']:
                code,body,ctype=self.http('/diagrams/'+name+'.html',auth=False)
                assert code==200 and 'text/html' in ctype
                assert body==(self.root/'diagrams'/f'{name}.html').read_bytes()
                hashes[name]=hashlib.sha256(body).hexdigest()
            self.mark('diagrams',http_sha256=hashes,scope='合成HTML托管，不替代D04/G02浏览器语义验收')
            self.compose('up','-d','--pull','never','--force-recreate','--wait','--wait-timeout',str(self.startup_timeout),timeout=self.startup_timeout+120)
            self.assert_data();self.mark('recreate',mysql_and_application_recreated=True,records_and_config_retained=True)
            self.env['H02_RELEASE']='v2'
            self.compose('build',timeout=900)
            self.compose('up','-d','--pull','never','--wait','--wait-timeout',str(self.startup_timeout),timeout=self.startup_timeout+120)
            assert self.data('/health',auth=False)['version']=='v2';self.assert_data()
            self.mark('upgrade',from_version='v1',to_version='v2',records_retained=True,schema_change=False)
            self.env['H02_RELEASE']='v1'
            self.compose('up','-d','--pull','never','--no-build','--wait','--wait-timeout',str(self.startup_timeout),timeout=self.startup_timeout+120)
            assert self.data('/health',auth=False)['version']=='v1';self.assert_data()
            self.mark('rollback',version='v1',known_compatible_schema=True,records_retained=True)
            backup=self.compose('exec','-T','mysql','sh','-c','MYSQL_PWD="$MYSQL_PASSWORD" mysqldump --no-tablespaces --single-transaction -u"$MYSQL_USER" "$MYSQL_DATABASE"',log=False).stdout
            # 在本次测试MySQL中创建另一空库，真实恢复SQL；不启动第二个高内存实例。
            self.compose('exec','-T','mysql','sh','-c','MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot -e "CREATE DATABASE h02restore"',log=False)
            self.compose('exec','-T','mysql','sh','-c','MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot h02restore',stdin=backup,log=False)
            rows=self.compose('exec','-T','mysql','sh','-c','MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot h02restore -N -e "SELECT id,name FROM items ORDER BY id"',log=False).stdout.decode().splitlines()
            assert rows==['api-probe\tsynthetic','mcp-probe\tsdk-created']
            self.mark('backup_restore',separate_database=True,same_mysql_instance=True,destination='h02restore',records=rows,backup_sha256=hashlib.sha256(backup).hexdigest())
            self.compose('stop','mysql')
            assert self.http('/health',auth=False)[0]==503
            self.compose('up','-d','--pull','never','--wait','--wait-timeout',str(self.startup_timeout),'mysql',timeout=self.startup_timeout+120)
            self.assert_data();self.mark('failure_recovery',injected='database_stopped',unavailable_health=503,recovered=True)
            self.capture_images()
            scanned={}
            for tag in self.tags:
                scanned[tag]=self.scan_image(tag)
            self.mark('secrets',synthetic_canaries=3,image_archives_bytes=scanned,scope='所有已构建应用版本的元数据与文件层')
        except BaseException as exc:
            primary=exc
            self.report['failure']={'type':type(exc).__name__,'message':str(exc)[:300]}
            try:self.compose('logs','--no-color','--tail','50',check=False)
            except BaseException as log_error:
                self.report['log_error']=type(log_error).__name__
                if isinstance(primary,Exception) and not isinstance(log_error,Exception):primary=log_error
        finally:
            cleanup_errors=[]
            # 每项独立执行：down失败或取消也必须继续精确标签回读。
            operations=[('down',lambda:self.compose('down','--volumes','--remove-orphans',timeout=180))]
            label='label=com.docker.compose.project='+self.project
            for name,args in [('containers',['docker','ps','-aq']),
                              ('volumes',['docker','volume','ls','-q']),
                              ('networks',['docker','network','ls','-q'])]:
                operations.append((name,lambda args=args:self.run(args+['--filter',label])))
            for tag in self.tags:
                operations.append(('image',lambda tag=tag:self.run(['docker','image','rm',tag])))
            for name,operation in operations:
                try:
                    result=operation()
                    if name in ('containers','volumes','networks') and result.stdout.strip():
                        raise RuntimeError('owned_resources_remaining')
                except BaseException as cleanup:
                    cleanup_errors.append({'step':name,'type':type(cleanup).__name__})
                    if not isinstance(cleanup,Exception) and (primary is None or isinstance(primary,Exception)):
                        primary=cleanup
            if cleanup_errors:self.report['cleanup_error']=cleanup_errors
            else:
                self.mark('cleanup',compose_project=self.project,containers=0,volumes=0,networks=0)
            self.report['finished_at']=now()
            self.report['passed']=not self.report.get('failure') and not self.report.get('cleanup_error') and {r['name'] for r in self.records}==set(STAGES)
            errors=[]
            try:
                dump(self.root/self.contract['docker']['evidence'],self.report)
                self.contract['checks'][0]['status']='passed' if self.report['passed'] else 'failed'
                dump(self.root/'project-contract.json',self.contract)
                validate_docker(self.root,self.contract,errors)
                dump(self.root/'verification/contract-check.json',{'passed':not errors,'errors':errors})
            except BaseException as evidence_error:
                if primary is None:primary=evidence_error
                else:primary.add_note('evidence_write_failed:'+type(evidence_error).__name__)
                errors.append('evidence_write_failed')
        if primary is not None and not isinstance(primary,Exception):raise primary
        return self.report['passed'] and not errors


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--mode',choices=['embedded','separate','both'],default='both')
    p.add_argument('--reuse-build-cache',action='store_true',help='修复后的重复演练可复用依赖层；首次保留默认干净构建')
    p.add_argument('--startup-timeout',type=int,default=900,help='首次数据库初始化的有界等待秒数，60至1800；不重置重试直到成功')
    a=p.parse_args()
    if not 60 <= a.startup_timeout <= 1800:p.error('startup-timeout应为60至1800')
    root=a.output_dir.resolve()
    if root.exists():raise SystemExit('output-dir必须是全新目录，避免覆盖已有证据或资源归属')
    root.mkdir(parents=True)
    preflight=probe();dump(root/'preflight.json',preflight)
    if not preflight['passed']:raise SystemExit('Docker预检失败；见preflight.json')
    before=subprocess.run(['docker','ps','-q'],capture_output=True,check=True).stdout.decode().split()
    images={}
    for key,tag in [('python','python:3.11-slim'),('node','node:24-slim'),('mysql','mysql:8.4')]:
        pulled=bounded_run(['docker','pull',tag],timeout=600)
        if pulled.returncode:raise RuntimeError('base_image_pull_failed:'+tag)
        data=json.loads(subprocess.run(['docker','image','inspect',tag],capture_output=True,check=True).stdout)[0]
        images[key]=data['RepoDigests'][0]
    results={}
    for mode in (['embedded','separate'] if a.mode=='both' else [a.mode]):
        results[mode]=Trial(root/mode,mode,images,a.reuse_build_cache,a.startup_timeout).execute()
        if not results[mode]:break
    after=subprocess.run(['docker','ps','-q'],capture_output=True,check=True).stdout.decode().split()
    retained=set(before)<=set(after)
    report={'passed':all(results.values()) and retained,'modes':results,'existing_running_containers_retained':retained,
            'existing_container_count':len(before),'scope':'真实Docker+合成业务；不包含两个真实系统、真实公网OAuth和数据库结构迁移验收'}
    dump(root/'summary.json',report);print(json.dumps(report,ensure_ascii=False),flush=True)
    raise SystemExit(0 if report['passed'] else 1)


if __name__=='__main__':main()
