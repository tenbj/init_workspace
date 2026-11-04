"""最终DDL/INSERT与字段合同核验。不根据源表或字段后缀猜目标类型。"""
import re


def unquote(value):
    if value[:1] in ('`', '"', "'"):
        q = value[0]
        return re.sub(r'\\(.)', r'\1', value[1:-1].replace(q+q, q))
    return value


def tokens(text):
    from validate_delivery import sql_parts
    return [v for k, v, _ in sql_parts(text) if k not in ('comment', 'hint')]


def paren_items(ts, start):
    depth, result, item = 1, [], []
    for j in range(start+1, len(ts)):
        t = ts[j]
        if t == '(':
            depth += 1
        elif t == ')':
            depth -= 1
            if not depth:
                if item:
                    result.append(item)
                return result, j
        if t == ',' and depth == 1:
            result.append(item)
            item = []
        else:
            item.append(t)
    raise ValueError('SQL括号未闭合')


def ddl_fields(text):
    ts = tokens(text)
    start = next(i for i in range(len(ts)-1) if ts[i].upper() == 'CREATE' and ts[i+1].upper() == 'TABLE')
    opening = ts.index('(', start)
    items, end = paren_items(ts, opening)
    fields = []
    for item in items:
        if item[0].upper() in ('INDEX','CONSTRAINT','PRIMARY','UNIQUE','KEY'):
            raise ValueError('不支持内联表约束，请明确Doris实体表字段定义')
        upper = [t.upper() for t in item]
        cut = next((i for i in range(1,len(item)) if upper[i] in ('NOT','NULL','COMMENT','DEFAULT')), None)
        if cut is None or 'COMMENT' not in upper:
            raise ValueError('DDL字段缺少显式可空或COMMENT：'+item[0])
        c = upper.index('COMMENT')
        fields.append({'name':unquote(item[0]), 'type':''.join(item[1:cut]).lower(),
                       'comment':unquote(item[c+1]), 'nullable':'NOT' not in upper[:c]})
    keys = []
    for i in range(end+1,len(ts)-2):
        if ts[i].upper() in ('UNIQUE','PRIMARY','DUPLICATE','AGGREGATE') and ts[i+1].upper()=='KEY':
            parts,_=paren_items(ts,i+2)
            if ts[i].upper() in ('UNIQUE','PRIMARY'):
                keys=[unquote(p[0]) for p in parts]
            break
    return fields, keys


def insert_fields(text):
    ts = tokens(text)
    lists=[]
    for i,t in enumerate(ts[:-2]):
        if t.upper()!='INSERT' or ts[i+1].upper() not in ('INTO','OVERWRITE'):
            continue
        j=i+2
        if ts[j].upper()=='TABLE':j+=1
        j+=1
        while j+1<len(ts) and ts[j]=='.':j+=2
        if j>=len(ts) or ts[j]!='(':
            raise ValueError('INSERT必须显式列出目标字段')
        parts,_=paren_items(ts,j)
        lists.append([unquote(p[0]) for p in parts if len(p)==1])
    if len(lists)!=1:
        raise ValueError('要求恰好一个显式列清单的INSERT')
    return lists[0]


def verify_contract(contract, ddl, sql):
    fields,keys=ddl_fields(ddl)
    expected=contract['fields']
    if [f['name'] for f in fields]!=[f['name'] for f in expected]:
        raise ValueError('最终DDL与字段合同的字段集合/顺序不一致')
    if insert_fields(sql)!=[f['name'] for f in fields]:
        raise ValueError('INSERT与最终DDL字段顺序不一致')
    for a,b in zip(fields,expected):
        for k in ('type','comment','nullable'):
            av,bv=a[k],b[k]
            if k=='type':av,bv=re.sub(r'\s+','',av),re.sub(r'\s+','',bv.lower())
            if av!=bv:raise ValueError(f"{a['name']}：最终DDL与合同{k}不一致")
    if keys!=[f['name'] for f in expected if f['physical_primary_key']]:
        raise ValueError('最终DDL物理主键与合同不一致')
    return fields,keys
