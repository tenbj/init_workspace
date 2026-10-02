"""校验交付合同、API覆盖和证据引用；不替代实际运行测试。"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re

REQUIRED=['README.md','CHANGELOG.md','LICENSE','.gitignore','.env.example',
          'requirements.txt','requirements-dev.txt','docs/API中文说明.md','docs/API中文说明.html',
          'docs/openapi.json','docs/AI接入与调用指南.md','docs/MCP工具目录.json',
          'examples/api_client.py','examples/mcp_client.py','scripts/configure_mcp.py',
          'scripts/build_release.py','.github/workflows/ci.yml']
CHECKS={'business','api','mcp','browser','persistence','portable','release_scan','architecture','erd'}


def safe_path(root, value):
    target=(root/value).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError('合同路径越出项目目录')
    return target


def validate_pages(root, contract, checks, errors):
    """核对两页与本轮实现快照；语义和浏览器检查仍由执行者负责。"""
    delivery = contract.get('delivery_id')
    if not isinstance(delivery, str) or not delivery.strip():
        errors.append('缺少本轮delivery_id')
    pages = contract.get('diagrams', {})
    seen = set()

    def relative_file(value):
        if not isinstance(value, str) or not value.strip() or Path(value).is_absolute() or Path(value).drive:
            raise ValueError('页面与来源必须使用项目内相对路径')
        target = safe_path(root, value)
        if not target.is_file():
            raise ValueError('文件不存在：' + value)
        return target

    def fingerprint(path, expected):
        return isinstance(expected, str) and re.fullmatch('[0-9a-f]{64}', expected) and hashlib.sha256(path.read_bytes()).hexdigest() == expected

    for kind, skill in [('architecture', 'D04'), ('erd', 'G02')]:
        try:
            page = pages.get(kind, {})
            if page.get('skill') != skill:
                raise ValueError('生成技能必须为' + skill)
            target = relative_file(page.get('path'))
            if target in seen:
                raise ValueError('架构与ER必须是两个独立HTML页面')
            seen.add(target)
            if target.suffix.lower() not in {'.html', '.htm'} or not re.search(r'<(?:html\b|!doctype\s+html\b)', target.read_text(encoding='utf-8-sig'), re.I):
                raise ValueError('交付物必须为HTML页面')
            if not fingerprint(target, page.get('sha256')):
                raise ValueError('页面SHA256过期或无效')
            if page.get('maintenance') not in {'created', 'updated', 'reviewed_unchanged'}:
                raise ValueError('缺少本轮维护状态')
            if not isinstance(page.get('change_note'), str) or not page['change_note'].strip():
                raise ValueError('缺少本轮变更或保持不变的说明')
            sources = page.get('sources')
            if not isinstance(sources, list) or not sources:
                raise ValueError('缺少实现或模型来源快照')
            for source in sources:
                source_path = relative_file(source.get('path'))
                if source_path == target:
                    raise ValueError('不能以页面自身作为实现来源')
                if not fingerprint(source_path, source.get('sha256')):
                    raise ValueError('实现或模型来源SHA256过期或无效')
            report_path = relative_file(checks.get(kind, {}).get('evidence'))
            report = json.loads(report_path.read_text(encoding='utf-8-sig'))
            if report.get('passed') is not True or report.get('source_consistent') is not True:
                raise ValueError('页面验收或实现一致性核对未通过')
            if report.get('delivery_id') != delivery or not delivery:
                raise ValueError('验收证据不属于本轮交付')
            if report.get('diagram_sha256') != page['sha256'] or report.get('sources') != sources:
                raise ValueError('验收证据与当前页面或来源不一致')
        except (ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            errors.append(kind + '页面：' + str(exc))


def validate(root):
    root=Path(root).resolve(); errors=[];warnings=[]
    for name in REQUIRED:
        if not (root/name).is_file():errors.append('缺少文件：'+name)
    for folder in ['tests','static']:
        if not (root/folder).is_dir() or not any((root/folder).iterdir()):errors.append('缺少实现或测试目录：'+folder)
    path=root/'project-contract.json'
    if not path.is_file():return {'passed':False,'errors':errors+['缺少project-contract.json'],'warnings':warnings}
    try:
        contract=json.loads(path.read_text(encoding='utf-8'))
        if contract.get('status')!='ready':errors.append('项目合同尚未ready')
        if not contract.get('project_name'):errors.append('缺少项目名称')
        if not re.fullmatch('[0-9a-f]{64}',contract.get('prototype',{}).get('sha256','')):errors.append('缺少有效原型SHA256')
        if contract.get('prototype',{}).get('source_modified') is not False:errors.append('原型保留状态必须明确为false')
        ops=contract.get('operations',[])
        if not ops:errors.append('没有业务操作映射')
        openapi=json.loads((root/'docs/openapi.json').read_text(encoding='utf-8')) if (root/'docs/openapi.json').exists() else {}
        catalog=json.loads((root/'docs/MCP工具目录.json').read_text(encoding='utf-8')) if (root/'docs/MCP工具目录.json').exists() else {}
        tools={t['name'] for t in catalog.get('tools',[])}
        mapped=set();mapped_tools=set()
        api_doc=(root/'docs/API中文说明.md').read_text(encoding='utf-8') if (root/'docs/API中文说明.md').exists() else ''
        for op in ops:
            method=op.get('method','').lower();route=op.get('path',''); key=(method,route)
            if key in mapped:errors.append('重复接口映射：'+str(key))
            mapped.add(key)
            definition=openapi.get('paths',{}).get(route,{}).get(method)
            if not definition:errors.append('OpenAPI不存在：'+str(key));continue
            if not re.search(r'[\u4e00-\u9fff]',definition.get('summary','')):errors.append('缺少中文summary：'+route)
            if route not in api_doc:errors.append('人类文档未覆盖：'+route)
            if not safe_path(root,op.get('python_example','')).is_file():errors.append('缺少Python示例：'+route)
            tool=op.get('mcp_tool')
            if tool:
                mapped_tools.add(tool)
                if tool not in tools:errors.append('目录中无MCP工具：'+tool)
        actual={(method,route) for route,methods in openapi.get('paths',{}).items() if route.startswith('/api/') for method in methods if method in {'get','post','put','patch','delete'}}
        if actual-mapped:errors.append('未映射业务API：'+str(sorted(actual-mapped)))
        if tools-mapped_tools:errors.append('未映射MCP工具：'+str(sorted(tools-mapped_tools)))
        checks={c['name']:c for c in contract.get('checks',[])}
        validate_pages(root, contract, checks, errors)
        for name in CHECKS:
            check=checks.get(name,{})
            if check.get('status')!='passed':errors.append('验收未通过：'+name)
            evidence=check.get('evidence','')
            if not evidence or not safe_path(root,evidence).is_file():errors.append('验收证据缺失：'+name)
        if checks.get('ai_task',{}).get('status')!='passed':warnings.append('尚未完成AI自主选择工具的任务验收，交付时必须明示')
        if not isinstance(contract.get('limits'),list):errors.append('缺少limits数组')
    except (ValueError,KeyError,TypeError,AttributeError,OSError) as exc:
        errors.append('合同格式错误：'+str(exc))
    return {'passed':not errors,'errors':errors,'warnings':warnings,
            'scope':'结构、映射、双HTML页面、来源哈希和本轮证据一致性；不替代实际语义核对与浏览器验收'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--project-dir',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    a=p.parse_args();r=validate(a.project_dir);a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(r,ensure_ascii=False));raise SystemExit(0 if r['passed'] else 1)
