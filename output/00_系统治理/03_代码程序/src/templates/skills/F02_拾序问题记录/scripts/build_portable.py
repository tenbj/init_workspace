"""Build a deterministic, instruction-only Skill from the F02 business source."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = '1.4.0'

def build(destination):
    destination.mkdir(parents=True, exist_ok=True)
    sources = {'SKILL.md': ROOT/'references/独立技能入口.md'}
    for name in ('录入与分类规则.md', '创建身份与模型规则.md'):
        sources['references/'+name] = ROOT/'references'/name
    target = destination/f'shixu-issues-{VERSION}.zip'
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, source in sources.items():
            data=source.read_text(encoding='utf-8').replace('\r\n','\n').encode('utf-8')
            info=zipfile.ZipInfo('shixu-issues/'+name,(2026,10,4,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(info,data)
        archive.writestr(zipfile.ZipInfo('shixu-issues/VERSION',(2026,10,4,0,0,0)),VERSION+'\n')
    result=dict(name='shixu-issues',version=VERSION,filename=target.name,sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                source='F02_拾序问题记录',sources={name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in sources.items()})
    (destination/'skill-manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    print(json.dumps(build(parser.parse_args().output),ensure_ascii=False))
