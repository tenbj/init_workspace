"""Read-only public HTTP checks; this is not a deployment or authenticated MCP test."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

LIMIT = 1024 * 1024


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def public_url(value):
    parsed = urlsplit(value)
    if (parsed.scheme not in ('http', 'https') or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment):
        raise ValueError('Use an HTTP(S) URL without credentials, query or fragment')
    return value


def check(url, kind, expected_version, version_field='version', skill_version=None):
    result = dict(kind=kind, url=public_url(url), passed=False)
    try:
        # Do not inherit proxy credentials or silently follow another endpoint.
        opener = build_opener(ProxyHandler({}), NoRedirect())
        with opener.open(Request(url, headers={'Accept': 'application/json, text/plain'}), timeout=10) as response:
            result['httpStatus'] = response.status
            body = response.read(LIMIT + 1)
            if response.status != 200:
                result['reason'] = 'unexpected_http_status'
                return result
            if len(body) > LIMIT:
                result['reason'] = 'response_too_large'
                return result
            if kind == 'updates':
                text = body.decode('utf-8-sig').strip()
                if (not text or 'html' in response.headers.get_content_type()
                        or text.lower().startswith(('<!doctype html', '<html'))):
                    result['reason'] = 'expected_nonempty_document'
                    return result
            else:
                data = json.loads(body)
                if kind == 'health' and isinstance(data, dict) and 'status' in data:
                    if str(data['status']).lower() not in ('ok', 'healthy', 'ready', 'pass', 'up'):
                        result['reason'] = 'unhealthy_status'
                        return result
                field = 'interfaceVersion' if kind == 'manifest' else version_field
                observed = data
                for part in field.split('.'):
                    observed = observed[part]
                if observed != expected_version:
                    result['reason'] = 'version_mismatch'
                    return result
                if kind == 'manifest' and skill_version and data['skill']['version'] != skill_version:
                    result['reason'] = 'skill_version_mismatch'
                    return result
        result['passed'] = True
    except HTTPError as error:
        result.update(httpStatus=error.code, reason='http_error')
        error.close()
    except Exception as error:
        # Exception messages and response bodies may contain secrets: omit both.
        result.update(reason='request_or_format_error', errorType=type(error).__name__)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--health-url', action='append', required=True, type=public_url)
    parser.add_argument('--expected-version', required=True)
    parser.add_argument('--version-field', default='version')
    parser.add_argument('--manifest-url', type=public_url)
    parser.add_argument('--expected-skill-version')
    parser.add_argument('--updates-url', type=public_url)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.expected_skill_version and not args.manifest_url:
        parser.error('--expected-skill-version requires --manifest-url')
    checks = [check(url, 'health', args.expected_version, args.version_field) for url in args.health_url]
    if args.manifest_url:
        checks.append(check(args.manifest_url, 'manifest', args.expected_version, skill_version=args.expected_skill_version))
    if args.updates_url:
        checks.append(check(args.updates_url, 'updates', args.expected_version))
    report = dict(scope='public-http-only', checkedAt=datetime.now(timezone.utc).isoformat(),
                  expectedVersion=args.expected_version, passed=all(item['passed'] for item in checks),
                  authenticatedBusinessAndMcp='not_checked', checks=checks)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(passed=report['passed'], checks=len(checks), scope=report['scope'])))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
