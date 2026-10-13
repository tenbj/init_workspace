"""验证演练工具的压缩镜像层扫描及有界超时，不需要Docker。"""
import gzip
import io
from pathlib import Path
import sys
import tarfile
import tempfile
import time
import unittest
from test_docker_runtime import bounded_run, scan_archive


class RunnerTests(unittest.TestCase):
    def test_secret_in_plain_and_compressed_layers_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'image.tar'
            for compress in [False,True]:
                for body,expected in [(b'clean-payload',False),(b'x'*1048568+b'synthetic-secret'+b'x'*30,True)]:
                    payload=gzip.compress(body) if compress else body
                    with tarfile.open(p,'w') as t:
                        info=tarfile.TarInfo('blobs/sha256/layer');info.size=len(payload);t.addfile(info,io.BytesIO(payload))
                    if expected:
                        with self.assertRaises(ValueError):scan_archive(p,[b'synthetic-secret'])
                    else:self.assertGreater(scan_archive(p,[b'synthetic-secret']),0)
            with tarfile.open(p,'w') as t:
                payload=b'\x28\xb5\x2f\xfdcompressed-zstd-fixture'
                info=tarfile.TarInfo('blobs/sha256/layer');info.size=len(payload);t.addfile(info,io.BytesIO(payload))
            with self.assertRaisesRegex(ValueError,'zstd_layer'):scan_archive(p,[b'synthetic-secret'])

    def test_timeout_terminates_child_holding_output_pipe(self):
        script="import subprocess,sys,time; subprocess.Popen([sys.executable,'-c','import time; time.sleep(120)']); print('started',flush=True); time.sleep(120)"
        started=time.monotonic()
        result=bounded_run([sys.executable,'-c',script],timeout=1)
        self.assertEqual(result.returncode,124)
        self.assertIn(b'started',result.stdout)
        self.assertLess(time.monotonic()-started,25)

    def test_success_retains_exit_and_output(self):
        result=bounded_run([sys.executable,'-c',"print('passed')"],timeout=10)
        self.assertEqual(result.returncode,0);self.assertIn(b'passed',result.stdout)


if __name__=='__main__':unittest.main()
