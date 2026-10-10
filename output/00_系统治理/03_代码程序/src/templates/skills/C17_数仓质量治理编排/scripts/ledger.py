"""Apply a versioned ledger change and rebuild the offline dashboard. Run B02 first."""
import argparse
import copy
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STAGES = ('C14', 'C15', 'C11')
STATES = {'未开始', '进行中', '已完成', '已有跳过', '待用户', '待补齐', '可重试错误', '已取消'}


def now():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def atomic_write(path, text):
    fd, name = tempfile.mkstemp(prefix='.write-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def merge(old, patch):
    result = copy.deepcopy(old)
    for key, value in patch.items():
        result[key] = merge(result[key], value) if isinstance(value, dict) and isinstance(result.get(key), dict) else value
    return result


def validate(data):
    for collection in ('models', 'batches', 'questions'):
        rows = data[collection]
        ids = [item['id'] for item in rows]
        if any(not value for value in ids) or len(ids) != len(set(ids)):
            raise ValueError(f'{collection}编号为空或重复')
    identities = []
    for model in data['models']:
        identity = [model.get(key) for key in ('connection', 'database', 'table')]
        if not model.get('table') or not model.get('sources'):
            raise ValueError('模型必须有技术表名与来源')
        if all(identity):
            identities.append(tuple(identity))
        for stage in STAGES:
            state = model['stages'][stage]
            if state['status'] not in STATES:
                raise ValueError('未知阶段状态')
            if state['status'] == '已有跳过' and stage != 'C15':
                raise ValueError('仅C15允许已有跳过')
            if state['status'] in ('已完成', '已有跳过') and not state.get('artifacts'):
                raise ValueError('完成或跳过必须有证据链接')
            if state['status'] == '已完成' and stage == 'C15':
                if state.get('sql_saved_readback_verified') is not True:
                    raise ValueError('C15完成必须确认正确模型的SQL已保存并回读一致')
            if state['status'] == '已完成' and stage == 'C11' and not state.get('conclusion'):
                raise ValueError('C11完成必须有明确结论')
        if model['stages']['C15']['status'] in ('进行中', '已完成') and model['stages']['C14']['status'] != '已完成':
            raise ValueError('C15配置依赖C14完成')
    if len(identities) != len(set(identities)):
        raise ValueError('同一连接/库/表重复登记，应合并来源')


def apply_change(current, change):
    if change['expected_revision'] != current['revision']:
        raise ValueError('台账版本已变化，请重读后合并，不覆盖其他修改')
    if not change.get('message') or not change.get('kind'):
        raise ValueError('每次变更必须说明事件类型与实际动作')
    result = copy.deepcopy(current)
    result['config'] = merge(result['config'], change.get('config', {}))
    for collection in ('models', 'batches', 'questions'):
        index = {item['id']: i for i, item in enumerate(result[collection])}
        for patch in change.get(collection, []):
            key = patch['id']
            if key in index:
                result[collection][index[key]] = merge(result[collection][index[key]], patch)
            else:
                value = copy.deepcopy(patch)
                if collection == 'models':
                    value.setdefault('in_scope', True)
                    value.setdefault('priority', 100)
                    value.setdefault('governance_result', '待确认')
                    value.setdefault('stages', {})
                    for stage in STAGES:
                        value['stages'].setdefault(stage, {'status': '未开始', 'artifacts': []})
                result[collection].append(value)
                index[key] = len(result[collection]) - 1
    result['revision'] += 1
    result['updated_at'] = now()
    result['events'].append({'id': f"E{result['revision']:06d}", 'at': result['updated_at'],
                             'revision': result['revision'], 'kind': change['kind'],
                             'message': change['message'], 'model_id': change.get('model_id'),
                             'stage': change.get('stage'), 'change': change})
    validate(result)
    return result


def render(data, root=ROOT):
    template = (Path(__file__).resolve().parent.parent / 'assets/看板模板.html').read_text(encoding='utf-8')
    payload = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    atomic_write(root / '治理进度看板.html', template.replace('__LEDGER_JSON__', payload))
    atomic_write(root / '执行日志.jsonl', ''.join(json.dumps(e, ensure_ascii=False) + '\n' for e in data['events']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--change', type=Path, help='变更JSON；省略时只重建展示')
    args = parser.parse_args()
    root = args.output_dir.resolve()
    lock = root / '.ledger.lock'
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.close(fd)
        path = root / '模型台账.json'
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        if args.change:
            change = json.loads(args.change.read_text(encoding='utf-8-sig'))
            data = apply_change(data, change)
            atomic_write(path, json.dumps(data, ensure_ascii=False, indent=2) + '\n')
        validate(data)
        render(data, root)
        print(json.dumps({'revision': data['revision'], 'models': len(data['models']),
                          'dashboard': str(root / '治理进度看板.html')}, ensure_ascii=False))
    finally:
        lock.unlink()


if __name__ == '__main__':
    main()
