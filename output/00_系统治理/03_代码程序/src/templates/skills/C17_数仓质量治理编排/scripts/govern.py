"""Quality batch ledger utilities. Run B02 before changing an existing output project."""
import argparse
import hashlib
import json
import re
import struct
import zlib
from datetime import datetime, timedelta
from pathlib import Path
import ledger


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def local_path(root, value):
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('证据路径必须位于输出目录内')
    return path


def schedule(source):
    if source.get('cycle') != 'daily':
        raise ValueError('非每日周期须核对日期/星期和跨日规则，不能擅自转每日')
    times = source.get('times', [])
    if not times or any(not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', t) for t in times):
        raise ValueError('必须提供现场读取的每日HH:MM时间列表')
    for key in ('observed_at', 'raw', 'source_enabled'):
        if key not in source:
            raise ValueError('缺少现场周期证据：' + key)
    last = max(times)
    hour, minute = map(int, last.split(':'))
    total = hour * 60 + minute + 5
    target = f'{total // 60 % 24:02d}:{total % 60:02d}'
    return {'rule': '模型更新周期最后配置时间+5分钟', 'offset_minutes': 5,
            'model_last_scheduled_time': last, 'monitor_time': target,
            'monitor_schedule': '每天 ' + target, 'day_offset': total // 1440,
            'source_enabled': source['source_enabled'], 'model_schedule_raw': source['raw'],
            'observed_at': source['observed_at'], 'status': '已推算待平台配置'}


def png_info(path):
    content = path.read_bytes()
    if len(content) < 33 or content[:8] != b'\x89PNG\r\n\x1a\n' or content[12:16] != b'IHDR':
        raise ValueError('截图必须是浏览器原始PNG文件')
    width, height = struct.unpack('>II', content[16:24])
    if width < 320 or height < 150:
        raise ValueError('截图尺寸不足以呈现模型与运行结果')
    offset, image_data, ended = 8, bytearray(), False
    while offset + 12 <= len(content):
        length = struct.unpack('>I', content[offset:offset+4])[0]
        kind = content[offset+4:offset+8]
        end = offset + 8 + length
        if end + 4 > len(content):
            raise ValueError('PNG内容被截断')
        if zlib.crc32(content[offset+4:end]) & 0xffffffff != struct.unpack('>I',content[end:end+4])[0]:
            raise ValueError('PNG内容校验失败')
        if kind == b'IDAT': image_data.extend(content[offset+8:end])
        offset = end + 4
        if kind == b'IEND': ended = True; break
    if not ended or not image_data:
        raise ValueError('PNG缺少完整图像内容')
    try:
        if not zlib.decompress(image_data): raise ValueError('PNG图像内容为空')
    except zlib.error as exc:
        raise ValueError('PNG图像内容损坏') from exc
    return {'sha256': hashlib.sha256(content).hexdigest(), 'width': width, 'height': height}


def check_capture(root, model, evidence):
    required = ('model_id', 'table', 'indicator_name', 'indicator_id', 'kind', 'path',
                'captured_at', 'run_at', 'result', 'quality_value', 'source_url',
                'identity_visible', 'result_visible', 'capture_method', 'execution_evidence')
    if any(k not in evidence for k in required):
        raise ValueError('截图元数据字段缺失')
    if evidence['model_id'] != model['id'] or evidence['table'] != model['table']:
        raise ValueError('截图模型身份不匹配')
    if evidence['kind'] not in ('consistency', 'uniqueness'):
        raise ValueError('未知指标类型')
    if evidence['result'] not in ('正常', '异常'):
        raise ValueError('截图必须有明确运行结果')
    if evidence['identity_visible'] is not True and not (evidence.get('identity_context_path') and evidence.get('identity_context_verified') is True):
        raise ValueError('模型身份需在主图或配套身份图中清晰可见')
    if evidence.get('identity_context_path'):
        context = png_info(local_path(root,evidence['identity_context_path']))
        if evidence.get('identity_context_sha256') and evidence['identity_context_sha256'] != context['sha256']:
            raise ValueError('配套身份图内容已改变')
        evidence = {**evidence, 'identity_context_sha256': context['sha256']}
    if evidence['result_visible'] is not True:
        raise ValueError('必须人工检查截图能识别目标和运行结果')
    if evidence['capture_method'] != 'browser_screenshot':
        raise ValueError('禁止以生成图或报告渲染替代平台截图')
    captured, ran = [datetime.fromisoformat(evidence[k].replace('Z', '+00:00')) for k in ('captured_at', 'run_at')]
    if not captured.tzinfo or not ran.tzinfo or captured < ran:
        raise ValueError('时间必须带时区且截图时间不得早于运行时间')
    from urllib.parse import urlsplit
    url = urlsplit(evidence['source_url'])
    if url.scheme not in ('http', 'https') or url.query or url.username or url.password:
        raise ValueError('来源只保留无凭证的页面地址')
    # Execution evidence is a separately captured platform record, not a timestamp inferred from the image.
    run = read(local_path(root, evidence['execution_evidence']))
    for key in ('model_id', 'table', 'indicator_id', 'indicator_name', 'run_at', 'result', 'quality_value'):
        if run.get(key) != evidence[key]:
            raise ValueError('运行证据与截图元数据不一致：' + key)
    if run.get('current_run_verified') is not True:
        raise ValueError('本次运行尚未核实')
    if run.get('selected_rows') != 1:
        raise ValueError('必须只运行目标1行')
    for key in ('submitted_at', 'observed_at'):
        if not run.get(key): raise ValueError('缺少运行时间证据：' + key)
    submitted, observed = [datetime.fromisoformat(run[k].replace('Z','+00:00')) for k in ('submitted_at','observed_at')]
    second_precision = run.get('platform_time_precision') == 'second' and ran.microsecond == 0
    after_submit = submitted < ran + timedelta(seconds=1) if second_precision else submitted <= ran
    if any(t.tzinfo is None for t in (submitted, observed)) or not (after_submit and ran <= observed <= captured):
        raise ValueError('提交、新旧结果、观察及截图时间链不成立')
    if run.get('previous_run_at'):
        previous = datetime.fromisoformat(run['previous_run_at'].replace('Z', '+00:00'))
        if previous.tzinfo is None or not previous < ran:
            raise ValueError('仍为历史运行结果或上次运行时间无时区')
    elif not (run.get('previous_run_at') is None
              and run.get('previous_run_absent_verified') is True
              and run.get('first_run_verified') is True
              and run.get('history_record_count') == 1
              and run.get('first_run_evidence')):
        raise ValueError('缺少上次运行时间，或首次运行的无历史及首条记录证据')
    actual = png_info(local_path(root, evidence['path']))
    if evidence.get('sha256') and evidence['sha256'] != actual['sha256']:
        raise ValueError('截图内容已改变')
    return {**evidence, **actual, 'status': '已留证'}


def batch_change(data, request, request_path):
    batch_id = request['id']
    if not re.fullmatch(r'B\d{4,}',batch_id):
        raise ValueError('批次编号格式为B加至少4位数字')
    if any(x['id'] == batch_id for x in data['batches']):
        raise ValueError('批次已存在，请恢复原批次而非重复登记')
    if int(batch_id[1:]) <= max([int(b['id'][1:]) for b in data['batches']] or [0]):
        raise ValueError('新批次编号必须大于既有最大值')
    if not request.get('models'):
        raise ValueError('批次模型清单不能为空')
    received = request.get('received_at') or ledger.now()
    models, seen = [], set()
    number = max([int(m['id'][1:]) for m in data['models']] or [0])
    for row in request['models']:
        identity = tuple(row.get(k, '') for k in ('connection', 'database', 'table'))
        if not all(identity) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', identity[2]):
            raise ValueError('模型须有连接、数据库与合法技术表名')
        if identity in seen:
            continue
        seen.add(identity)
        old = next((m for m in data['models'] if tuple(m.get(k) for k in ('connection','database','table')) == identity), None)
        source = {'batch_id': batch_id, 'location': request_path, 'received_at': received,
                  'skip': bool(row.get('skip')), 'note': row.get('note', '')}
        if old:
            models.append({'id': old['id'], 'sources': old['sources'] + [source]})
            continue
        number += 1
        model = {**row, 'id': f'M{number:04d}', 'round_id': 'R001', 'sources': [source],
                 'in_scope': not source['skip'], 'current_action': '待执行',
                 'uniqueness': {'status': '未开始', 'artifacts': []}}
        if source['skip']:
            model.update(scope_status='用户指定跳过', current_action=source['note'] or '用户指定跳过',
                         stages={s: {'status': '已取消', 'artifacts': []} for s in ledger.STAGES},
                         uniqueness={'status': '用户指定跳过', 'artifacts': []})
        models.append(model)
    return {'expected_revision': data['revision'], 'kind': '接收批次', 'message': request.get('name', batch_id),
            'batches': [{'id': batch_id, 'name': request.get('name', ''), 'received_at': received,
                         'source_path': request_path, 'model_count': len(seen)}], 'models': models}


def verify(root, data, batch_id, model_id=None):
    issues, checked = [], 0
    for model in data['models']:
        sources = [s for s in model['sources'] if s['batch_id'] == batch_id]
        if not sources or (model_id and model['id'] != model_id) or sources[-1].get('skip') or model['in_scope'] is False:
            continue
        for kind, state in [('consistency', model['stages']['C15']), ('uniqueness', model.get('uniqueness', {}))]:
            if kind == 'uniqueness' and state.get('status') in ('不适用', '用户指定跳过'):
                continue
            checked += 1
            captures = [s for s in model.get('screenshots', []) if s.get('batch_id') == batch_id and s.get('kind') == kind]
            try:
                if not captures:
                    raise ValueError('待运行截图')
                check_capture(root, model, captures[-1])
            except (ValueError, OSError, KeyError) as exc:
                issues.append({'model_id': model['id'], 'kind': kind, 'reason': str(exc)})
    return {'batch_id': batch_id, 'model_id': model_id, 'checked': checked,
            'passed': checked > 0 and not issues, 'issues': issues}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True, type=Path)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('init')
    sub.add_parser('render')
    sub.add_parser('batch').add_argument('--input', required=True, type=Path)
    sub.add_parser('schedule').add_argument('--input', required=True, type=Path)
    sub.add_parser('attach').add_argument('--input', required=True, type=Path)
    v = sub.add_parser('verify'); v.add_argument('--batch', required=True); v.add_argument('--model')
    args = parser.parse_args(); root = args.output_dir.resolve()
    if args.command == 'schedule':
        print(json.dumps(schedule(read(args.input)), ensure_ascii=False, indent=2)); return
    if args.command == 'init':
        root.mkdir(parents=True, exist_ok=True)
        path = root / '模型台账.json'
        if path.exists():
            raise ValueError('台账已存在，请使用render或恢复任务')
        data = {'revision': 0, 'updated_at': ledger.now(), 'config': {'schedule_rule':'model_last_plus_5'},
                'models': [], 'batches': [], 'questions': [], 'events': []}
        ledger.atomic_write(path, json.dumps(data, ensure_ascii=False, indent=2)); ledger.render(data, root); return
    if args.command == 'verify':
        result = verify(root, read(root / '模型台账.json'), args.batch, args.model)
        print(json.dumps(result, ensure_ascii=False, indent=2)); raise SystemExit(0 if result['passed'] else 1)
    # A single lock covers read, change validation, ledger commit and rendering.
    import os
    lock = root / '.ledger.lock'; fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.close(fd); data = read(root / '模型台账.json'); change = None
        if args.command == 'batch':
            source = args.input.resolve()
            if not source.is_relative_to(root):
                raise ValueError('请先将清单原件保存到输出目录内')
            change = batch_change(data, read(source), source.relative_to(root).as_posix())
        if args.command == 'attach':
            evidence = read(args.input)
            model = next(m for m in data['models'] if m['id'] == evidence['model_id'])
            if not any(s['batch_id'] == evidence.get('batch_id') for s in model['sources']):
                raise ValueError('截图批次不属于该模型')
            checked = check_capture(root, model, evidence)
            captures = model.get('screenshots', [])
            if any(c.get('path') == checked['path'] for c in captures):
                raise ValueError('截图已登记，请保留原证据，勿重复追加')
            patch = {'id': model['id'], 'screenshots': captures + [checked]}
            state = model['stages']['C15'] if checked['kind'] == 'consistency' else model.get('uniqueness', {}).get('execution', {})
            previous_latest = state.get('latest_at')
            if not previous_latest or datetime.fromisoformat(checked['run_at'].replace('Z','+00:00')) >= datetime.fromisoformat(previous_latest.replace('Z','+00:00')):
                latest = {'result': checked['result'], 'quality_value': checked['quality_value'],
                          'latest_at': checked['run_at'], 'result_origin': '已核实运行并截图留证',
                          'execution_evidence': checked['execution_evidence']}
                if checked['kind'] == 'consistency': patch['stages'] = {'C15': latest}
                else: patch['uniqueness'] = {'execution': latest}
            change = {'expected_revision': data['revision'], 'kind': '运行截图',
                      'message': model['id'] + ' 已登记平台运行截图', 'model_id': model['id'],
                      'models': [patch]}
        if change:
            data = ledger.apply_change(data, change)
            ledger.atomic_write(root / '模型台账.json', json.dumps(data, ensure_ascii=False, indent=2))
        ledger.validate(data); ledger.render(data, root)
        print(json.dumps({'revision': data['revision'], 'dashboard': str(root / '治理进度看板.html')}, ensure_ascii=False))
    finally:
        lock.unlink()


if __name__ == '__main__':
    main()
