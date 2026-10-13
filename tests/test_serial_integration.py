"""POSIX pseudo-terminal integration tests; install requirements.txt to run."""
import importlib.util
import os
import select
import subprocess
import sys
import time
import unittest
from pathlib import Path


@unittest.skipUnless(os.name == 'posix' and importlib.util.find_spec('serial'),
                     'requires POSIX and pyserial')
class SerialIntegrationTests(unittest.TestCase):
    def test_usb_stream_then_manual_fallback(self):
        import pty
        master, slave = pty.openpty()
        script = Path(__file__).resolve().parents[1] / 'simulator' / 'rf_channel_sim.py'
        process = subprocess.Popen(
            [sys.executable, '-u', str(script), '--port', os.ttyname(slave)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True)
        try:
            deadline = time.monotonic() + 5
            data = b''
            while b'STATUS\n' not in data and time.monotonic() < deadline:
                if select.select([master], [], [], 0.1)[0]:
                    data += os.read(master, 1024)
            self.assertIn(b'STATUS\n', data)
            os.write(master, b'boot noise\nSTATE ON\nSTATUS\n')
            # Wait for the next poll, proving the prior read cycle completed.
            self.assertTrue(select.select([master], [], [], 3)[0])
            os.read(master, 1024)
            os.close(master)
            master = None
            stdout, stderr = process.communicate('status\nquit\n', timeout=8)
            self.assertEqual(process.returncode, 0, stderr)
            self.assertIn('[TEST]', stdout)
            self.assertIn('Falling back to manual', stdout)
            self.assertIn('[NORMAL]', stdout)
            self.assertIn('Serial unavailable', stderr)
        finally:
            if master is not None:
                os.close(master)
            os.close(slave)
            if process.poll() is None:
                process.kill()
                process.communicate()

    def test_missing_port_fallback(self):
        script = Path(__file__).resolve().parents[1] / 'simulator' / 'rf_channel_sim.py'
        result = subprocess.run(
            [sys.executable, str(script), '--port', '/nonexistent/embedded-rf-port'],
            input='on\nstatus\nquit\n', text=True, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0)
        self.assertIn('Falling back to manual', result.stdout)
        self.assertIn('[TEST]', result.stdout)
