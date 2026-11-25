from __future__ import annotations

import json
import sys
import unittest
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from secure_aggregation import aggregate_masked_updates, generate_keypair, mask_update, pair_mask, validate_masked_payload
from common import init_model, local_train


class SecureAggregationTests(unittest.TestCase):
    def test_pair_derives_identical_mask(self):
        private_a, public_a = generate_keypair()
        private_b, public_b = generate_keypair()
        mask_a = pair_mask(private_a, public_b, pair_id="a|b", parameter="w", round_id="r1", shape=(8,))
        mask_b = pair_mask(private_b, public_a, pair_id="a|b", parameter="w", round_id="r1", shape=(8,))
        np.testing.assert_allclose(mask_a, mask_b, rtol=0.0, atol=0.0)

    def test_three_client_masks_cancel(self):
        pairs = {client: generate_keypair() for client in ("a", "b", "c")}
        roster = {client: pair[1] for client, pair in pairs.items()}
        updates = {
            "a": {"w": np.asarray([1.0, 2.0]), "b": np.asarray([0.5])},
            "b": {"w": np.asarray([-3.0, 1.0]), "b": np.asarray([1.5])},
            "c": {"w": np.asarray([4.0, -5.0]), "b": np.asarray([-0.5])},
        }
        masked = [mask_update(client, pairs[client][0], roster, updates[client], round_id="r1") for client in updates]
        aggregate = aggregate_masked_updates(masked)
        for name in aggregate:
            expected = sum(update[name] for update in updates.values())
            np.testing.assert_allclose(aggregate[name], expected, rtol=0.0, atol=3e-15)

    def test_coordinator_payload_rejects_plaintext_field(self):
        valid = {"phase": "masked_update", "client_id": "a", "pid": 1, "samples": 2, "masked_update": {"w": [1.0]}}
        validate_masked_payload(valid)
        with self.assertRaises(ValueError):
            validate_masked_payload({**valid, "plaintext_update": {"w": [1.0]}})

    def test_class_balancing_handles_missing_local_class_without_warning(self):
        model = init_model(2, 3, 3, seed=1)
        x = np.asarray([[0.0, 1.0], [1.0, 0.0]])
        y = np.asarray([0, 0])
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            trained = local_train(model, x, y, epochs=1, lr=0.01, batch_size=2, seed=1, class_balance=True)
        self.assertTrue(all(np.isfinite(value).all() for value in trained.values()))

    def test_frozen_protocol_and_dp_statuses(self):
        secure = json.loads((ROOT / "runs" / "secure-aggregation-v1" / "metrics.json").read_text(encoding="utf-8"))
        self.assertEqual(secure["status"], "protocol_passed_utility_below_deployment_gate")
        self.assertEqual(secure["real_clients"], 7)
        self.assertFalse(secure["coordinator_received_private_keys"])
        self.assertFalse(secure["coordinator_received_plaintext_updates"])
        self.assertTrue(secure["secure_and_plaintext_predictions_identical"])

        private = json.loads((ROOT / "runs" / "dp-output-perturbation-v1" / "metrics.json").read_text(encoding="utf-8"))
        self.assertEqual(private["status"], "rejected")
        self.assertLess(private["sample_dp_output_perturbation"]["macro_f1"], private["gate"]["minimum_macro_f1"])
        self.assertIn("not participant-level DP", private["privacy_scope"])


if __name__ == "__main__":
    unittest.main()
