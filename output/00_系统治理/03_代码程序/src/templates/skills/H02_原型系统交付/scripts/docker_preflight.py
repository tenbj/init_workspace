"""只读Docker环境预检；不启动桌面、拉取镜像、修改context或清理资源。"""
import argparse
import json
from pathlib import Path
import subprocess


def probe():
    report = {'passed': False, 'checks': {}, 'scope': 'CLI/Engine/Compose可用性，不等于项目部署成功'}
    for name, args in [('engine', ['docker', 'version', '--format', '{{json .}}']),
                       ('compose', ['docker', 'compose', 'version', '--short'])]:
        try:
            p = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
            if p.returncode:
                report['checks'][name] = {'passed': False, 'error': 'command_failed', 'exit_code': p.returncode}
            elif name == 'engine':
                data = json.loads(p.stdout)
                report['checks'][name] = {'passed': bool(data.get('Server')),
                    'client': data.get('Client', {}).get('Version'),
                    'server': data.get('Server', {}).get('Version'),
                    'os': data.get('Server', {}).get('Os'), 'arch': data.get('Server', {}).get('Arch')}
            else:
                report['checks'][name] = {'passed': True, 'version': p.stdout.strip()}
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            report['checks'][name] = {'passed': False, 'error': type(exc).__name__}
    report['passed'] = all(c['passed'] for c in report['checks'].values())
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report', type=Path, required=True)
    a = p.parse_args()
    result = probe()
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result['passed'] else 1)
