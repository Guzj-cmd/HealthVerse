from __future__ import annotations

import json
import sys
import threading
import unittest
import urllib.request
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import aggregate, clip_update, model_to_json, sign_body
from coordinator import State, handler_factory
from http.server import ThreadingHTTPServer


class FederatedTest(unittest.TestCase):
    def test_clip_and_weighted_average(self):
        model = {"w": np.zeros(2)}
        clipped, raw_norm, factor = clip_update({"w": np.asarray([3.0, 4.0])}, 2.5)
        self.assertAlmostEqual(raw_norm, 5.0); self.assertAlmostEqual(factor, 0.5)
        result = aggregate(model, [(1, clipped), (3, {"w": np.zeros(2)})])
        np.testing.assert_allclose(result["w"], np.asarray([0.375, 0.5]))

    def test_two_local_clients_do_not_claim_multi_device(self):
        secret = "test-secret"
        state = State(secret, input_dim=3, hidden_dim=2, classes=2, min_clients=2, clip_norm=5.0)
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler_factory(state))
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        base = f"http://127.0.0.1:{server.server_port}"

        def post(path, value):
            body = json.dumps(value).encode()
            request = urllib.request.Request(base + path, data=body, method="POST", headers={"X-HV-Signature": sign_body(secret, body)})
            with urllib.request.urlopen(request) as response: return json.load(response)

        fingerprint = "a" * 64
        clients = [post("/register", {"device_fingerprint": fingerprint})["client_id"] for _ in range(2)]
        zero = {key: np.zeros_like(value) for key, value in state.model.items()}
        for client_id in clients:
            post("/update", {"client_id": client_id, "round_token": state.token(client_id), "sample_count": 3, "update": model_to_json(zero)})
        self.assertEqual(state.status()["run_type"], "local_federated_test")
        self.assertEqual(state.completed_rounds[0]["distinct_device_fingerprints"], 1)
        server.shutdown(); server.server_close()


if __name__ == "__main__": unittest.main()
