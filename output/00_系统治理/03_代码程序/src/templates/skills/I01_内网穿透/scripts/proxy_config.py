"""Plan/apply one TCP proxy without leaking secrets or restarting services."""
import argparse
from datetime import datetime
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import tomllib


def build(source, name, ip, local, remote, maximum=14999):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}',name):
        raise ValueError('Invalid proxy name')
    ipaddress.ip_address(ip)
    if not 1<=local<=65535 or not 1<=remote<=min(maximum,65535):
        raise ValueError('Port outside permitted range')
    original=tomllib.loads(source)
    proxies=original.get('proxies',[])
    names=[p['name'] for p in proxies]
    if len(names)!=len(set(names)):
        raise ValueError('Duplicate proxy names')
    if any(p['name']!=name and p.get('remotePort')==remote for p in proxies):
        raise ValueError('Remote port occupied by another proxy')
    target=next((p for p in proxies if p['name']==name),None)
    desired={'localIP':ip,'localPort':local,'remotePort':remote}
    nl='\r\n' if '\r\n' in source else '\n'
    if target and target.get('type')!='tcp':
        raise ValueError('Existing proxy is not TCP')
    changed=not target or any(target.get(k)!=v for k,v in desired.items())
    if not changed:
        return source,dict(proxy=name,**desired,changed=False)
    if not target:
        values={'name':name,'type':'tcp',**desired}
        result=source.rstrip('\r\n')+nl+nl+'[[proxies]]'+nl+nl.join(f'{k} = {json.dumps(v)}' for k,v in values.items())+nl
    else:
        starts=list(re.finditer(r'(?m)^[ \t]*\[\[proxies\]\][ \t]*(?:#.*)?\r?$',source))
        candidates=[]
        for i,m in enumerate(starts):
            end=starts[i+1].start() if i+1<len(starts) else len(source)
            block=source[m.start():end]
            if re.search(r'(?m)^[ \t]*name\s*=\s*'+re.escape(json.dumps(name))+r'[ \t]*(?:#.*)?\r?$',block):
                candidates.append((m.start(),end,block))
        if len(candidates)!=1:
            raise ValueError('Unsupported target block layout')
        start,end,block=candidates[0]
        for key,value in desired.items():
            pattern=r'(?m)^([ \t]*'+key+r'[ \t]*=[ \t]*)([^#\r\n]*)([^\r\n]*)(\r?)$'
            if re.search(pattern,block):
                block=re.sub(pattern,lambda m:m[1]+json.dumps(value)+(' ' if m[3].startswith('#') else '')+m[3]+m[4],block)
            else:
                if '[' in block.split('[[proxies]]',1)[1]:
                    raise ValueError('Missing field in block with subtables')
                block=block.rstrip('\r\n')+nl+f'{key} = {json.dumps(value)}'+nl
        result=source[:start]+block+source[end:]
    updated=tomllib.loads(result)
    actual=next(p for p in updated['proxies'] if p['name']==name)
    if any(actual[k]!=v for k,v in desired.items()):
        raise ValueError('Target verification failed')
    if {k:v for k,v in original.items() if k!='proxies'}!={k:v for k,v in updated.items() if k!='proxies'}:
        raise ValueError('Unrelated settings changed')
    if [p for p in proxies if p['name']!=name]!=[p for p in updated['proxies'] if p['name']!=name]:
        raise ValueError('Unrelated proxies changed')
    if target and {k:v for k,v in target.items() if k not in desired}!={k:v for k,v in actual.items() if k not in desired}:
        raise ValueError('Other target settings changed')
    return result,dict(proxy=name,**desired,changed=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['plan','apply'])
    p.add_argument('--config',type=Path,required=True)
    p.add_argument('--name',required=True)
    p.add_argument('--local-ip',default='127.0.0.1')
    p.add_argument('--local-port',type=int,required=True)
    p.add_argument('--remote-port',type=int,required=True)
    p.add_argument('--max-port',type=int,default=14999)
    p.add_argument('--frpc',type=Path)
    p.add_argument('--output',type=Path)
    args=p.parse_args()
    old=args.config.read_bytes()
    text,report=build(old.decode('utf-8-sig'),args.name,args.local_ip,args.local_port,args.remote_port,args.max_port)
    report.update(action=args.action,config=str(args.config.resolve()))
    if args.action=='apply' and report['changed']:
        if not args.frpc or not args.frpc.is_file():
            raise ValueError('apply requires --frpc')
        candidate=None
        try:
            with tempfile.NamedTemporaryFile(dir=args.config.parent,suffix='.toml',delete=False) as f:
                candidate=Path(f.name)
                f.write((b'\xef\xbb\xbf' if old.startswith(b'\xef\xbb\xbf') else b'')+text.encode('utf-8'))
            checked=subprocess.run([str(args.frpc.resolve()),'verify','-c',str(candidate.resolve())],capture_output=True,timeout=30)
            if checked.returncode:
                raise ValueError('Candidate frpc validation failed')
            if args.config.read_bytes()!=old:
                raise ValueError('Concurrent modification detected')
            backup=args.config.with_name(args.config.name+'.bak-'+datetime.now().strftime('%Y%m%d%H%M%S%f'))
            shutil.copyfile(args.config,backup)
            if backup.read_bytes()!=old:
                raise ValueError('Backup mismatch')
            shutil.copymode(args.config,candidate)
            os.replace(candidate,args.config)
            report.update(backup=str(backup.resolve()),config_verified=True)
        finally:
            if candidate:
                candidate.unlink(missing_ok=True)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    try:
        main()
    except (ValueError,OSError,subprocess.TimeoutExpired) as error:
        # No parser/subprocess diagnostics: they can include secret source lines.
        raise SystemExit('Config operation failed; inspect inputs and validation locally. Original credentials are not printed.') from None
