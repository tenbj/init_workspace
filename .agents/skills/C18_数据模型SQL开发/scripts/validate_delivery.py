"""检查实体表五件交付及中文 SQL 注释；不连接数据库。"""
import argparse
import hashlib
import json
import re
from pathlib import Path


def sql_parts(sql):
    """分离注释与代码词元，保留字符串；支持常见 SQL 引号及转义。"""
    parts = []
    i = 0
    while i < len(sql):
        start = i
        if sql[i].isspace():
            i += 1
            continue
        if sql.startswith('--', i) or sql[i] == '#':
            end = sql.find('\n', i)
            i = len(sql) if end < 0 else end
            parts.append(('comment', sql[start:i], start))
        elif sql.startswith('/*', i):
            end = sql.find('*/', i + 2)
            if end < 0:
                raise ValueError('SQL块注释未闭合')
            i = end + 2
            kind = 'hint' if sql.startswith(('/*+', '/*!'), start) else 'comment'
            parts.append((kind, sql[start:i], start))
        elif sql[i] in "'\"`":
            quote = sql[i]
            i += 1
            while i < len(sql):
                if sql[i] == '\\':
                    i += 2
                elif sql[i] == quote:
                    i += 1
                    if i < len(sql) and sql[i] == quote:
                        i += 1
                    else:
                        break
                else:
                    i += 1
            else:
                raise ValueError('SQL字符串或标识符未闭合')
            parts.append(('quoted', sql[start:i], start))
        else:
            match = re.match(r'[A-Za-z0-9_]+', sql[i:])
            i += len(match.group()) if match else 1
            parts.append(('code', sql[start:i], start))
    return parts


def chinese_comment_errors(sql):
    parts = sql_parts(sql)
    errors = []
    previous = None
    for kind, value, offset in parts:
        is_description = kind == 'comment' or (
            kind == 'quoted' and value[0] in "'\"" and previous == 'COMMENT')
        if is_description and re.search(r'[A-Za-z\u3400-\u9fff]', value):
            if not re.search(r'[\u3400-\u9fff]', value):
                errors.append({'line': sql.count('\n', 0, offset) + 1,
                               'message': '说明性注释需使用中文', 'text': value[:150]})
        if kind not in ('comment', 'hint'):
            previous = value.upper()
    return errors


def cte_comma_errors(sql):
    """仅检查 WITH 列表分隔逗号；忽略字符串、注释和子查询内部逗号。"""
    tokens = [p for p in sql_parts(sql) if p[0] not in ('comment', 'hint')]
    errors = []
    for i, (kind, value, _) in enumerate(tokens):
        if kind != 'code' or value.upper() != 'WITH':
            continue
        j = i + 1
        if j < len(tokens) and tokens[j][1].upper() == 'RECURSIVE':
            j += 1
        while j + 2 < len(tokens):
            # CTE 名称后允许列名列表。
            k = j + 1
            if tokens[k][1] == '(':
                depth = 1
                k += 1
                while k < len(tokens) and depth:
                    if tokens[k][0] == 'code':
                        depth += (tokens[k][1] == '(') - (tokens[k][1] == ')')
                    k += 1
            if k + 1 >= len(tokens) or tokens[k][1].upper() != 'AS' or tokens[k + 1][1] != '(':
                break
            k += 2
            depth = 1
            while k < len(tokens) and depth:
                if tokens[k][0] == 'code':
                    depth += (tokens[k][1] == '(') - (tokens[k][1] == ')')
                k += 1
            if k >= len(tokens) or tokens[k][1] != ',':
                break
            offset = tokens[k][2]
            line_start = sql.rfind('\n', 0, offset) + 1
            next_offset = tokens[k + 1][2] if k + 1 < len(tokens) else len(sql)
            between = sql[offset + 1:next_offset]
            if sql[line_start:offset].strip() or '\n' in between or between.strip():
                errors.append({'line': sql.count('\n', 0, offset) + 1,
                               'message': 'CTE分隔逗号须前置于下一CTE名称同一行；分段注释放在该行之前'})
            j = k + 1
    return errors


def blank_line_errors(sql):
    return [{'line': i, 'message': 'SQL文件不允许空白行；使用中文注释分段'}
            for i, line in enumerate(sql.splitlines(), 1) if not line.strip()]


def target_field_name_errors(sql):
    """只检查 CREATE 列定义和 INSERT 显式列；不限制源表或中间别名。"""
    tokens = [p for p in sql_parts(sql) if p[0] not in ('comment', 'hint')]
    errors = []
    for i, (kind, value, _) in enumerate(tokens):
        if kind != 'code' or value.upper() not in ('CREATE', 'INSERT'):
            continue
        j = i + 1
        if value.upper() == 'CREATE':
            if j >= len(tokens) or tokens[j][1].upper() != 'TABLE':
                continue
            j += 1
            if j < len(tokens) and tokens[j][1].upper() == 'IF':
                j += 3  # IF NOT EXISTS
        else:
            if j >= len(tokens) or tokens[j][1].upper() != 'INTO':
                continue
            j += 1
        if j >= len(tokens):
            continue
        j += 1  # 表名，可以为库名.表名。
        while j + 1 < len(tokens) and tokens[j][1] == '.':
            j += 2
        if j >= len(tokens) or tokens[j][1] != '(':
            continue
        depth, expect_name = 1, True
        for kind, token, offset in tokens[j + 1:]:
            if kind == 'code' and token == ')':
                depth -= 1
                if depth == 0:
                    break
            if expect_name and depth == 1:
                name = token.strip('`"')
                if name.upper() not in ('CONSTRAINT', 'PRIMARY', 'UNIQUE', 'KEY', 'INDEX', 'CHECK', 'FOREIGN'):
                    if not re.fullmatch(r'[a-z][a-z0-9]*(?:_[a-z0-9]+)*', name):
                        errors.append({'line': sql.count('\n', 0, offset) + 1,
                                       'message': '目标字段须使用小写下划线形式，并按E03审核语义', 'field': name})
                expect_name = False
            if kind == 'code' and token == '(':
                depth += 1
            if kind == 'code' and token == ',' and depth == 1:
                expect_name = True
    return errors


def validate(folder, table):
    folder = Path(folder).resolve()
    if not re.fullmatch(r'[a-z][a-z0-9_]*', table):
        raise ValueError('表名须为不含库名的小写标识符')
    expected = {'交付说明.md',
                f'01_SQL/{table}/create_{table}.sql',
                f'01_SQL/{table}/{table}.sql',
                f'02_字段文档/{table}_字段信息.xlsx',
                f'02_字段文档/{table}_平台字段信息.xlsx'}
    errors = []
    files = {p.relative_to(folder).as_posix(): p for p in folder.rglob('*') if p.is_file()}
    for missing in sorted(expected - files.keys()):
        errors.append({'file': missing, 'message': '缺少必需交付文件'})
    for extra in sorted(files.keys() - expected):
        errors.append({'file': extra, 'message': '正式交付存在清单外文件'})
    hashes = {}
    for name, path in sorted(files.items()):
        if not path.resolve().is_relative_to(folder):
            errors.append({'file': name, 'message': '链接指向交付目录外'})
            continue
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        if path.stat().st_size == 0:
            errors.append({'file': name, 'message': '交付文件为空'})
        if path.suffix.lower() in ('.sql', '.md'):
            sql = path.read_text(encoding='utf-8-sig')
            if re.search(r'\{\{[^{}]+\}\}|\[TODO\b', sql):
                errors.append({'file': name, 'message': '残留模板占位符'})
            if path.suffix.lower() == '.sql':
                try:
                    errors.extend(dict(file=name, **e) for e in chinese_comment_errors(sql))
                    errors.extend(dict(file=name, **e) for e in cte_comma_errors(sql))
                    errors.extend(dict(file=name, **e) for e in blank_line_errors(sql))
                    errors.extend(dict(file=name, **e) for e in target_field_name_errors(sql))
                except ValueError as exc:
                    errors.append({'file': name, 'message': str(exc)})
    return {'status': 'PASS' if not errors else 'FAIL', 'table': table,
            'file_count': len(files), 'errors': errors, 'sha256': hashes,
            'scope': '仅文件清单、命名路径、中文注释、无空白行、CTE逗号前置、CREATE/INSERT目标字段命名形式、占位符；未验证SQL执行和字段语义'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--delivery-dir', required=True)
    parser.add_argument('--table', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    folder, output = Path(args.delivery_dir).resolve(), Path(args.output).resolve()
    if output.is_relative_to(folder):
        parser.error('校验报告必须保存在正式交付目录外')
    if not folder.is_dir():
        parser.error('正式交付目录不存在')
    try:
        result = validate(folder, args.table)
    except (ValueError, OSError, UnicodeError) as exc:
        parser.error(str(exc))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status': result['status'], 'errors': len(result['errors']),
                      'report': str(output)}, ensure_ascii=False))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
