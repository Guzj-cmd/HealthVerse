from __future__ import annotations

import json
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class NetworkProcessIntegrationTest(unittest.TestCase):
    def test_two_local_client_processes_remain_local_test(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0)); port = probe.getsockname()[1]
        secret = "integration-test-secret"
        server = subprocess.Popen([
            sys.executable, str(ROOT / "coordinator.py"), "--port", str(port), "--secret", secret,
            "--input-dim", "99", "--hidden-dim", "4", "--classes", "2", "--min-clients", "2",
        ], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.time() + 5
            while True:
                try:
                    urllib.request.urlopen(f"http://127.0.0.1:{port}/status", timeout=.2); break
                except Exception:
                    if time.time() > deadline: self.fail("coordinator did not start")
                    time.sleep(.1)
            with tempfile.TemporaryDirectory() as temp:
                data = Path(temp) / "local.jsonl"
                with data.open("w", encoding="utf-8") as handle:
                    for index in range(8):
                        points = [{"x": i * .01 + index * .0001, "y": i * .02, "z": i * .001} for i in range(33)]
                        handle.write(json.dumps({"subject_id": "local-subject", "label": "A" if index % 2 == 0 else "B", "landmarks": points}) + "\n")
                command = [sys.executable, str(ROOT / "client.py"), "--server", f"http://127.0.0.1:{port}",
                           "--secret", secret, "--data", str(data), "--subject-id", "local-subject", "--epochs", "1"]
                subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True, timeout=15)
                subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True, timeout=15)
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/status") as response: status = json.load(response)
            self.assertEqual(status["run_type"], "local_federated_test")
            self.assertEqual(status["completed_rounds"][0]["distinct_device_fingerprints"], 1)
        finally:
            server.terminate()
            try: server.wait(timeout=3)
            except subprocess.TimeoutExpired: server.kill()
            if server.stdout: server.stdout.close()
            if server.stderr: server.stderr.close()


if __name__ == "__main__": unittest.main()
