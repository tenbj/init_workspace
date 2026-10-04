"""Exercise deployment HTTP gates against an isolated loopback server."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest

from verify_http import check, main, public_url


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == '/redirect':
            self.send_response(302)
            self.send_header('Location', '/health')
            self.end_headers()
            return
        payloads = {
            '/health': ('application/json', '{"version":"3.2.0"}'),
            '/old': ('application/json', '{"version":"3.1.0"}'),
            '/unhealthy': ('application/json', '{"version":"3.2.0","status":"error"}'),
            '/manifest': ('application/json', '{"interfaceVersion":"3.2.0","skill":{"version":"1.5.0"}}'),
            '/updates': ('text/plain', '# Upgrade instructions'),
            '/login': ('text/html', '<html>Login</html>'),
            '/broken': ('application/json', '{"private":"sentinel-secret"'),
        }
        if self.path not in payloads:
            self.send_error(404)
            return
        kind, value = payloads[self.path]
        self.send_response(200)
        self.send_header('Content-Type', kind)
        self.end_headers()
        self.wfile.write(value.encode())


class HttpChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = 'http://127.0.0.1:' + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_complete_public_report_has_explicit_authentication_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'report.json'
            code = main(['--health-url', self.base + '/health', '--expected-version', '3.2.0',
                         '--manifest-url', self.base + '/manifest', '--expected-skill-version', '1.5.0',
                         '--updates-url', self.base + '/updates', '--output', str(output)])
            report = json.loads(output.read_text())
            self.assertEqual(code, 0)
            self.assertTrue(report['passed'])
            self.assertEqual(report['authenticatedBusinessAndMcp'], 'not_checked')

    def test_old_process_causes_nonzero_exit_even_with_new_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'report.json'
            code = main(['--health-url', self.base + '/old', '--expected-version', '3.2.0',
                         '--manifest-url', self.base + '/manifest', '--output', str(output)])
            self.assertEqual(code, 1)
            self.assertFalse(json.loads(output.read_text())['passed'])

    def test_stale_skill_is_rejected(self):
        self.assertEqual(check(self.base + '/manifest', 'manifest', '3.2.0', skill_version='1.6.0')['reason'], 'skill_version_mismatch')

    def test_target_version_does_not_hide_unhealthy_status(self):
        self.assertEqual(check(self.base + '/unhealthy', 'health', '3.2.0')['reason'], 'unhealthy_status')

    def test_login_redirect_missing_and_invalid_json_fail_closed(self):
        for path, kind in [('/login', 'updates'), ('/redirect', 'health'), ('/missing', 'health'), ('/broken', 'health')]:
            with self.subTest(path=path):
                result = check(self.base + path, kind, '3.2.0')
                self.assertFalse(result['passed'])
                self.assertNotIn('sentinel-secret', json.dumps(result))

    def test_secret_bearing_urls_are_rejected(self):
        for url in ['https://u:secret@example.com/', 'https://example.com/?token=secret', 'file:///private', 'https://example.com/#secret']:
            with self.assertRaises(ValueError):
                public_url(url)


if __name__ == '__main__':
    unittest.main()
