"""从最终字段合同和DDL生成平台六列导入Excel；旧11列猜测式生成已停用。"""
import argparse
import json
from pathlib import Path
import subprocess
import sys


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('contract','ddl','dwd-sql','output','work-dir','node'):
        p.add_argument('--'+arg,required=True)
    p.add_argument('--template',help='默认使用C18保存的平台六列模板')
    a=p.parse_args()
    skills=Path(__file__).resolve().parents[2]
    matches=list(skills.glob('C18_*'))
    if len(matches)!=1:p.error('C18目录须唯一')
    c18=matches[0]
    sys.path.insert(0,str(c18/'scripts'))
    from platform_contract import verify_contract
    from validate_platform_fields import validate
    contract_path=Path(a.contract).resolve()
    contract=json.loads(contract_path.read_text(encoding='utf-8-sig'))
    ddl=Path(a.ddl).read_text(encoding='utf-8-sig')
    sql=Path(a.dwd_sql).read_text(encoding='utf-8-sig')
    verify_contract(contract,ddl,sql)
    template=Path(a.template).resolve() if a.template else c18/'assets/平台字段信息模板.xlsx'
    output,work=Path(a.output).resolve(),Path(a.work_dir).resolve()
    if output in (template,contract_path,Path(a.ddl).resolve(),Path(a.dwd_sql).resolve()):
        p.error('输出不能覆盖模板或输入')
    if output.suffix.lower()!='.xlsx':p.error('输出必须为xlsx')
    work.mkdir(parents=True,exist_ok=True)
    if not (work/'node_modules/@oai/artifact-tool').exists():
        p.error('先按load_workspace_dependencies结果在work-dir建立node_modules链接，不得使用仓库依赖')
    payload={'contract':contract,'template':str(template),'output':str(output),
             'receipt':str(work/'平台字段生成回执.json'),'previewDir':str(work/'预览')}
    input_file=work/'平台字段生成输入.json'
    input_file.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8')
    runner=work/'run_platform_fields.mjs'
    runner.write_text("import fs from 'node:fs/promises';\nimport * as artifact from '@oai/artifact-tool';\n"
        +f"import {{buildPlatformFields}} from {json.dumps((c18/'scripts/build_platform_fields.mjs').as_uri())};\n"
        +"const args=JSON.parse(await fs.readFile(process.argv[2],'utf8'));\n"
        +"console.log(JSON.stringify(await buildPlatformFields({...args,artifact})));\n",encoding='utf-8')
    subprocess.run([str(Path(a.node).resolve()),str(runner),str(input_file)],check=True)
    result=validate(output,contract,ddl,sql)
    (work/'平台字段校验.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':result['status'],'fields':result['field_count'],'output':str(output)},ensure_ascii=False))
    return 0 if result['status']=='PASS' else 1


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except (ValueError,OSError,KeyError,subprocess.CalledProcessError) as exc:
        print(str(exc),file=sys.stderr)
        raise SystemExit(1)
