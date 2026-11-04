"""以真实导入件验证拦截能力；坏样本仅放临时目录，不改正式交付。"""
import argparse
import copy
import json
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from validate_platform_fields import validate
from platform_contract import ddl_fields, insert_fields

NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main'


def corrupt(source,target,cell,value=None,drop_row=None):
    with zipfile.ZipFile(source) as src,zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as out:
        for entry in src.infolist():
            data=src.read(entry.filename)
            if entry.filename=='xl/worksheets/sheet1.xml':
                root=ET.fromstring(data)
                if drop_row:
                    parent=root.find(f'{{{NS}}}sheetData')
                    row=next(e for e in parent if e.get('r')==str(drop_row))
                    parent.remove(row)
                else:
                    c=next(e for e in root.iter(f'{{{NS}}}c') if e.get('r')==cell)
                    c.clear();c.set('r',cell);c.set('t','inlineStr')
                    ET.SubElement(ET.SubElement(c,f'{{{NS}}}is'),f'{{{NS}}}t').text=value
                data=ET.tostring(root,encoding='utf-8',xml_declaration=True)
            out.writestr(entry,data)


def main():
    p=argparse.ArgumentParser()
    for key in ('excel','ddl','sql','contract','output'):p.add_argument('--'+key,required=True)
    a=p.parse_args()
    contract=json.loads(Path(a.contract).read_text(encoding='utf-8-sig'))
    ddl=Path(a.ddl).read_text(encoding='utf-8-sig')
    sql=Path(a.sql).read_text(encoding='utf-8-sig')
    results=[]
    baseline=validate(a.excel,contract,ddl,sql)
    results.append({'case':'输入字段合同对应的导入件','passed':baseline['status']=='PASS'})
    cases=[('错误表头','A1','旧排序列',None),('错误精度','B5','varchar(20)',None),
           ('错误COMMENT','E5','错误释义',None),('错误中文名','D5','错误名称',None),
           ('丢失物理主键','F5','',None),('错误业务序号','A5','0',None),
           ('缺失字段',None,None,6),('审计错序','C2','etl_dt',None)]
    with tempfile.TemporaryDirectory(prefix='platform-fields-') as d:
        for i,(name,cell,value,row) in enumerate(cases):
            dest=Path(d)/f'{i}.xlsx';corrupt(a.excel,dest,cell,value,row)
            r=validate(dest,contract,ddl,sql)
            results.append({'case':name,'passed':r['status']=='FAIL','errors':r['errors']})
    bad=copy.deepcopy(contract);bad['fields'][0]['physical_primary_key']=False
    r=validate(a.excel,bad,ddl,sql)
    results.append({'case':'合同与DDL物理键冲突','passed':r['status']=='FAIL'})
    names=insert_fields(sql)
    swapped=sql.replace('`'+names[0]+'`,','`wrong_target`,',1)
    r=validate(a.excel,contract,ddl,swapped)
    results.append({'case':'INSERT列名错位','passed':r['status']=='FAIL'})
    example="CREATE TABLE x (`key_a` int NOT NULL COMMENT '键一', `key_b` varchar(255) NOT NULL COMMENT '键二', `amt` decimal(18, 6) NULL COMMENT '金额，含逗号和''引号') UNIQUE KEY(`key_a`,`key_b`) DISTRIBUTED BY HASH(`key_a`) BUCKETS 24"
    f,k=ddl_fields(example)
    results.append({'case':'复合键/小数逗号/中文注释/SQL转义解析','passed':k==['key_a','key_b'] and f[-1]['type']=='decimal(18,6)' and f[-1]['comment']=="金额，含逗号和'引号"})
    result={'status':'PASS' if all(r['passed'] for r in results) else 'FAIL','checks':results}
    Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':result['status'],'cases':len(results)},ensure_ascii=False))
    return 0 if result['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
