"""官方dws消息助手：默认只预检，明确execute才发送；持久化防重和真实回执。"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

MARK = '（codex自动发送）'


class DeliveryError(Exception):
    pass


def call(dws, profile, args):
    """所有钉钉调用均经CLI；不输出含敏感信息的原始stderr。"""
    try:
        p = subprocess.run([dws, *args, '--profile', profile, '--format', 'json', '--timeout', '15'],
                           capture_output=True, timeout=25)
        data = json.loads(p.stdout.decode('utf-8-sig'))
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise DeliveryError(type(exc).__name__) from None
    if p.returncode:
        raise DeliveryError('dws_exit_' + str(p.returncode))
    return data


def body(data):
    value = data.get('data') if 'ok' in data and isinstance(data.get('data'), dict) else data
    if not isinstance(value, dict):
        raise DeliveryError('invalid_response')
    return value


def choose(data, name, identity=None):
    payload = body(data)
    rows = payload.get('result')
    if payload.get('success') is not True or not isinstance(rows, list):
        raise DeliveryError('contact_query_failed')
    found = [r for r in rows if isinstance(r, dict) and name in [r.get('name'), r.get('nick')]]
    if identity:
        found = [r for r in found if r.get('openDingTalkId') == identity]
    if len(found) != 1 or not found[0].get('openDingTalkId'):
        raise DeliveryError('recipient_not_unique_or_unverified')
    return {'name': name, 'openDingTalkId': found[0]['openDingTalkId']}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


def save(path, receipt):
    receipt['updated_at'] = datetime.now(timezone.utc).isoformat()
    tmp = path.with_name(path.name + '.writing')
    with tmp.open('w', encoding='utf-8') as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)


def poll(args, receipt, path):
    for attempt in range(3):
        try:
            response = body(call(args.dws, args.profile, ['chat', 'message', 'query-send-status',
                                                        '--open-task-id', receipt['openTaskId']]))
        except DeliveryError as exc:
            receipt.update(status='pending', error=str(exc))
            save(path, receipt)
            return receipt
        result = response.get('result')
        result = result if isinstance(result, dict) else {}
        status = result.get('sendStatus')
        receipt['sendStatus'] = status
        for key in ['openMessageId', 'openConversationId']:
            if result.get(key):
                receipt[key] = result[key]
        if response.get('success') is True and status == 'SUCCESS':
            receipt.update(status='success', error=None)
        elif status in ['FAILED', 'FAIL', 'FAILURE']:
            receipt.update(status='failed', error='remote_send_failed')
        else:
            receipt.update(status='pending', error=None)
        save(path, receipt)
        if receipt['status'] != 'pending':
            return receipt
        if attempt < 2:
            time.sleep(1)
    return receipt


def run(args):
    content = Path(args.content_file).read_text(encoding='utf-8-sig')
    if not content.strip() or '{真实MR链接}' in content or '<已核对真实MR链接>' in content:
        raise DeliveryError('empty_content_or_unfilled_template')
    if MARK not in content:
        content += MARK
    request = {'profile': args.profile, 'recipient_name': args.recipient_name,
               'recipient_id_filter': args.recipient_id, 'request_id': args.request_id, 'content': content}
    path = Path(args.receipt).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + '.lock')
    try:
        handle = lock.open('x', encoding='utf-8')
    except FileExistsError:
        raise DeliveryError('receipt_locked_do_not_resend') from None
    try:
        handle.write(str(os.getpid()))
        handle.close()
        if path.exists():
            receipt = json.loads(path.read_text(encoding='utf-8-sig'))
            if receipt.get('request_digest') != digest(request):
                raise DeliveryError('receipt_belongs_to_different_request')
            if receipt.get('status') == 'success':
                return receipt
            if receipt.get('openTaskId'):
                return poll(args, receipt, path) if args.execute else receipt
            if receipt.get('status') in ['send_started', 'unknown', 'failed']:
                raise DeliveryError('prior_send_unresolved_do_not_resend')
        else:
            receipt = dict(request, request_digest=digest(request), status='prepared')
        contact = choose(call(args.dws, args.profile, ['contact', 'user', 'search', '--query', args.recipient_name]),
                         args.recipient_name, args.recipient_id)
        if receipt.get('recipient') and receipt['recipient'] != contact:
            raise DeliveryError('recipient_changed_since_prepare')
        receipt['recipient'] = contact
        receipt['idempotency_key'] = 'f03-' + digest([args.profile, args.request_id, contact, content])
        save(path, receipt)
        if not args.execute:
            return receipt
        # 先落发送中状态；即使进程崩溃，复跑也不会盲目再发送。
        receipt['status'] = 'send_started'
        save(path, receipt)
        try:
            response = body(call(args.dws, args.profile, ['chat', 'message', 'send', '--open-dingtalk-id',
                contact['openDingTalkId'], '--content', content, '--idempotency-key', receipt['idempotency_key']]))
            result = response.get('result')
            task = result.get('openTaskId') if isinstance(result, dict) else None
            if response.get('success') is not True or not task:
                raise DeliveryError('send_without_confirmed_task')
        except DeliveryError as exc:
            receipt.update(status='unknown', error=str(exc))
            save(path, receipt)
            return receipt
        receipt.update(status='pending', openTaskId=task)
        save(path, receipt)
        return poll(args, receipt, path)
    finally:
        if not handle.closed:
            handle.close()
        lock.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dws', default='dws')
    parser.add_argument('--profile', required=True)
    parser.add_argument('--recipient-name', required=True)
    parser.add_argument('--recipient-id')
    parser.add_argument('--content-file', required=True)
    parser.add_argument('--request-id', required=True)
    parser.add_argument('--receipt', required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    try:
        receipt = run(args)
        print(json.dumps({k: receipt.get(k) for k in ['status', 'recipient_name', 'openTaskId', 'sendStatus',
                                                     'openMessageId', 'error']}, ensure_ascii=False))
        return 0 if receipt['status'] in ['prepared', 'success'] else 2
    except (DeliveryError, OSError, ValueError) as exc:
        print(json.dumps({'status': 'blocked', 'error': str(exc)}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
