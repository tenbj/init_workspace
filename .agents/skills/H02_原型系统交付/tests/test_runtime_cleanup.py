"""Offline process-tree and cancellation regressions; never invokes Docker."""
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import test_docker_runtime as runtime


class ProcessCleanupTests(unittest.TestCase):
    def exercise(self, cancellation):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ready, late = root / 'ready', root / 'late'
            child = ('from pathlib import Path; import time; '
                     f'Path({str(ready)!r}).write_text("ready"); time.sleep(8); '
                     f'Path({str(late)!r}).write_text("orphan")')
            parent = ('import subprocess, sys; '
                      f'p=subprocess.Popen([sys.executable,"-c",{child!r}]); p.wait()')
            real_popen = subprocess.Popen
            roots = []

            def launch(*args, **kwargs):
                process = real_popen(*args, **kwargs)
                if not roots:
                    roots.append(process)
                    communicate = process.communicate
                    first = True

                    def interrupt(*values, **options):
                        nonlocal first
                        if first and cancellation is not None:
                            first = False
                            deadline = time.monotonic() + 10
                            while not ready.exists() and time.monotonic() < deadline:
                                time.sleep(.01)
                            if not ready.exists():
                                raise AssertionError('synthetic child did not start')
                            raise cancellation
                        return communicate(*values, **options)

                    process.communicate = interrupt
                return process

            with patch.object(runtime.subprocess, 'Popen', side_effect=launch):
                if cancellation is None:
                    result = runtime.bounded_run([sys.executable, '-c', parent], timeout=.5)
                    self.assertEqual(result.returncode, 124)
                else:
                    with self.assertRaises(type(cancellation)) as raised:
                        runtime.bounded_run([sys.executable, '-c', parent], timeout=10)
                    self.assertIs(raised.exception, cancellation)
            self.assertTrue(ready.exists())
            self.assertIsNotNone(roots[0].poll())
            time.sleep(8.1)
            self.assertFalse(late.exists(), 'child survived command cancellation')

    def test_keyboard_interrupt_reaps_real_child(self):
        self.exercise(KeyboardInterrupt())

    def test_system_exit_reaps_real_child(self):
        self.exercise(SystemExit(7))

    def test_timeout_reaps_real_child(self):
        self.exercise(None)


class TrialCleanupTests(unittest.TestCase):
    def exercise(self, original, fail_logs=False, fail_down=False, residual=False,
                 fail_evidence=False):
        with tempfile.TemporaryDirectory() as directory:
            trial = runtime.Trial(Path(directory), 'embedded', {})
            calls = []
            trial.contract = {'docker': {'evidence': 'verification/report.json'},
                              'checks': [{'status': 'pending'}]}

            def compose(*args, **kwargs):
                calls.append(args[0])
                if args[0] == 'config':
                    raise original
                if args[0] == 'logs' and fail_logs:
                    raise RuntimeError('logs unavailable')
                if args[0] == 'down' and fail_down:
                    raise RuntimeError('down unavailable')
                return subprocess.CompletedProcess(args, 0, b'', b'')

            def run(args, **kwargs):
                self.assertEqual(args[-1], 'label=com.docker.compose.project=' + trial.project)
                calls.append(args[1])
                return subprocess.CompletedProcess(args, 0, b'remaining' if residual else b'', b'')

            with patch.object(trial, 'prepare'), patch.object(trial, 'compose', side_effect=compose), \
                 patch.object(trial, 'run', side_effect=run), \
                 patch.object(runtime, 'validate_docker'), \
                 patch.object(runtime, 'dump', side_effect=OSError('disk failure') if fail_evidence else None):
                if not isinstance(original, Exception):
                    with self.assertRaises(type(original)) as raised:
                        trial.execute()
                    self.assertIs(raised.exception, original)
                else:
                    self.assertFalse(trial.execute())
            self.assertEqual(calls, ['config', 'logs', 'down', 'ps', 'volume', 'network'])
            self.assertFalse(trial.report['passed'])
            if fail_down or residual:
                self.assertIn('cleanup_error', trial.report)
                self.assertNotIn('cleanup', [record['name'] for record in trial.records])

    def test_keyboard_interrupt_is_not_swallowed(self):
        self.exercise(KeyboardInterrupt())

    def test_system_exit_is_not_swallowed(self):
        self.exercise(SystemExit(9))

    def test_logs_and_down_failures_do_not_skip_label_readback(self):
        self.exercise(RuntimeError('initial failure'), fail_logs=True, fail_down=True)

    def test_remaining_resources_fail_cleanup(self):
        self.exercise(RuntimeError('initial failure'), residual=True)

    def test_evidence_failure_does_not_replace_cancellation(self):
        self.exercise(KeyboardInterrupt(), fail_evidence=True)


if __name__ == '__main__':
    unittest.main()
