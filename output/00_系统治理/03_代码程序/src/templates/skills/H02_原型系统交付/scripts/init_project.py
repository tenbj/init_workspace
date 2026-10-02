"""建立原型系统交付骨架；实际业务实现由执行此Skill的AI继续完成。"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
from uuid import uuid4


def initialize(prototype: Path, project_name: str, output_dir: Path):
    source = prototype.resolve(strict=True)
    if not source.is_file() or source.suffix.lower() not in {'.html','.htm'}:
        raise ValueError('prototype必须指向可读取的HTML原型文件')
    target = output_dir.resolve()
    if target.exists() and any(target.iterdir()):
        raise ValueError('输出目录已存在且非空，禁止覆盖；请指定新目录')
    if not project_name.strip() or len(project_name)>100:
        raise ValueError('project-name必须为1至100字符')
    target.mkdir(parents=True,exist_ok=True)
    for folder in ['docs','docs/diagrams','examples','scripts','tests','static','data','verification','private']:
        (target/folder).mkdir(exist_ok=True)
    shutil.copyfile(source,target/'private/prototype.html')
    html=source.read_text(encoding='utf-8-sig')
    titles=re.findall(r'<title[^>]*>(.*?)</title>',html,re.I|re.S)
    contract={
        'schema_version':'1.1','project_name':project_name,'status':'draft',
        'delivery_id':str(uuid4()),
        'diagrams':{kind:dict(skill=skill,path=f'docs/diagrams/{kind}.html',sha256='',maintenance='not_run',change_note='',sources=[]) for kind,skill in [('architecture','D04'),('erd','G02')]},
        'prototype':{'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'title':titles[0].strip() if titles else '',
                     'private_copy':'private/prototype.html','source_modified':False},
        'operations':[],
        'checks':[{'name':name,'status':'not_run','evidence':''} for name in
                  ['business','api','mcp','browser','persistence','portable','release_scan','architecture','erd','ai_task']],
        'limits':[],
        'next_action':'AI读取原型，完成业务映射与系统实现，首次调用D04/G02生成架构与ER两个HTML页面并完成本轮验收；骨架不代表功能完成。'}
    (target/'project-contract.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2),encoding='utf-8')
    (target/'.gitignore').write_text('.env\n.env.*\n!.env.example\nprivate/\nruntime/\nverification/\n__pycache__/\n.pytest_cache/\n.venv/\nrelease/\n*.zip\n',encoding='utf-8')
    (target/'docs/需求与能力映射.md').write_text(
        '# 需求与能力映射\n\n状态：待实现。原型保存在被忽略的private目录，禁止未经确认发布其中业务数据。\n\n'
        '| 页面动作 | 业务对象 | API | MCP工具 | 输入与校验 | 保存与回读 | 验收证据 |\n'
        '|---|---|---|---|---|---|---|\n\n'
        '由AI逐项填写并实现，将机器映射同步到project-contract.json。\n',encoding='utf-8')
    return contract


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prototype',type=Path,required=True)
    p.add_argument('--project-name',required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args()
    result=initialize(a.prototype,a.project_name,a.output_dir)
    print(json.dumps({'output':str(a.output_dir.resolve()),'status':result['status'],'next':result['next_action']},ensure_ascii=False))


if __name__=='__main__':
    main()
