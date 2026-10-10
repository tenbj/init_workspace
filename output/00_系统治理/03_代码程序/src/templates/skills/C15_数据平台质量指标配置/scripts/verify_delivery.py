"""Check recorded platform evidence; this does not operate or observe a browser."""
import argparse
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path


def normalized_sql(text):
    return text.replace('\r\n', '\n').replace('\r', '\n')


def timestamp(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError('时间必须包含时区')
    return result


def validate(evidence, expected_sql=None, saved_sql=None, check='platform'):
    errors = []

    def require(ok, message):
        if not ok:
            errors.append(message)

    expected = evidence.get('expected') or {}
    actual = evidence.get('actual') or {}
    require(bool(evidence.get('evidence_refs')), '缺少现场证据引用')
    require(evidence.get('model_identity_verified') is True, '尚未核实模型身份')
    for key in ('indicator_name', 'model_key', 'model_cn', 'domain', 'layer'):
        require(bool(expected.get(key)), f'缺少目标字段：{key}')
        require(actual.get(key) == expected.get(key), f'身份不一致：{key}')
    action = evidence.get('action')
    if action == 'skipped_existing':
        require(type(evidence.get('existing_exact_count')) is int
                and evidence['existing_exact_count'] == 1, '已有指标未唯一匹配')
        if check != 'platform':
            errors.append('已有跳过只确认查重处理，不代表通知或运行已验证')
        return {'passed': not errors, 'action': action, 'check': check, 'errors': errors}
    require(action in ('created', 'updated'), '任务尚未完成或动作类型未知')
    require(evidence.get('saved_readback') is True, '缺少保存后回读')
    require(expected.get('connection') == '跨境电商', '连接应为跨境电商')
    require(expected.get('rule') == '自定义策略', '规则应为自定义策略')
    for key in ('connection', 'rule', 'condition'):
        require(bool(expected.get(key)), f'缺少目标配置：{key}')
        require(actual.get(key) == expected.get(key), f'保存值不一致：{key}')
    hashes = {}
    if not isinstance(expected_sql, str) or not isinstance(saved_sql, str):
        errors.append('缺少原始SQL或保存后SQL全文')
    else:
        source, saved = normalized_sql(expected_sql), normalized_sql(saved_sql)
        require(bool(source.strip()), '原始SQL为空')
        require(source == saved, 'SQL全文不一致（仅允许换行差异）')
        hashes = {key: hashlib.sha256(value.encode('utf-8')).hexdigest()
                  for key, value in [('expected_sha256', source), ('saved_sha256', saved)]}
    platform_errors = errors
    errors = []
    notifications = actual.get('notifications')
    notification_errors = [] if isinstance(notifications, list) and '钉钉-工作通知' in notifications else ['未选中钉钉-工作通知']
    run = evidence.get('execution') or {}
    require(type(run.get('selected_rows')) is int and run['selected_rows'] == 1,
            '执行时必须只选中一条数据行')
    require(run.get('target_model_key') == expected.get('model_key'), '运行目标模型不一致')
    require(run.get('target_indicator_name') == expected.get('indicator_name'), '运行目标指标不一致')
    require(run.get('submitted') is True, '未确认运行已提交')
    require(run.get('current_run_verified') is True and bool(run.get('linkage_evidence')),
            '结果未与本次提交关联')
    require(run.get('latest_result') in ('正常', '异常'), '尚无本次正常/异常结果')
    try:
        trigger = timestamp(run['triggered_at'])
        latest = timestamp(run['latest_at'])
        observed = timestamp(run['observed_at'])
        # A UI timestamp displayed to seconds denotes a one-second interval.
        # Keep the original millisecond submission time; never rewrite it backwards.
        second_precision = run.get('platform_time_precision') == 'second' and latest.microsecond == 0
        after_submit = trigger < latest + timedelta(seconds=1) if second_precision else trigger <= latest
        require(after_submit and latest <= observed, '结果时间不属于本次观察窗口')
        if run.get('previous_at'):
            require(timestamp(run['previous_at']) < latest, '仍为历史监控结果')
    except (KeyError, TypeError, ValueError):
        errors.append('缺少有效且带时区的执行时间')
    execution_errors = errors
    if check not in ('platform', 'notification', 'execution'):
        raise ValueError('未知核验项')
    selected = platform_errors + {'platform': [], 'notification': notification_errors,
                                  'execution': execution_errors}[check]
    return {'passed': not selected, 'action': action, 'check': check, 'errors': selected,
            'platform_passed': not platform_errors, 'notification_passed': not notification_errors,
            'execution_passed': not execution_errors, 'notification_errors': notification_errors,
            'execution_errors': execution_errors, **hashes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', required=True, type=Path)
    parser.add_argument('--expected-sql', type=Path)
    parser.add_argument('--saved-sql', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--check', choices=('platform', 'notification', 'execution'), default='platform')
    args = parser.parse_args()
    try:
        evidence = json.loads(args.evidence.read_text(encoding='utf-8-sig'))
        if not isinstance(evidence, dict):
            raise ValueError('证据必须为JSON对象')
        source = args.expected_sql.read_text(encoding='utf-8') if args.expected_sql else None
        saved = args.saved_sql.read_text(encoding='utf-8') if args.saved_sql else None
        report = validate(evidence, source, saved, args.check)
        code = 0 if report['passed'] else 1
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        report, code = {'passed': False, 'errors': [str(exc)]}, 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
