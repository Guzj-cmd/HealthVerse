from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evidence_gate import decide


class _Classifier:
    classes_ = np.asarray(["ask_confirm", "no_action"])


class _Model:
    named_steps = {"classifier": _Classifier()}

    def __init__(self, probability):
        self.probability = probability

    def predict_proba(self, _):
        return np.asarray([self.probability], dtype=float)


VALID = {
    "source_model_status": "passed",
    "predicted_relation": "seated_contact",
    "object": "chair",
    "frame_consistency": 0.9,
}


class EvidenceGateTests(unittest.TestCase):
    def test_unpassed_upstream_evidence_requests_confirmation(self):
        context = {**VALID, "source_model_status": "failed"}
        decision = decide(_Model([0.01, 0.99]), context)
        self.assertEqual(decision["immutable_action"], "ask_confirm")
        self.assertEqual(decision["evidence_codes"], ["source_model_not_passed"])

    def test_low_confidence_no_action_requests_confirmation(self):
        decision = decide(_Model([0.40, 0.60]), VALID)
        self.assertEqual(decision["immutable_action"], "ask_confirm")
        self.assertEqual(decision["policy_state"], "low_confidence_fallback")

    def test_contract_has_no_mutating_action(self):
        contract = json.loads((ROOT / "evidence_gate_contract.json").read_text(encoding="utf-8"))
        self.assertEqual(set(contract["output"]["immutable_action"]), {"no_action", "ask_confirm"})
        self.assertFalse(set(contract["output"]["immutable_action"]) & set(contract["unsupported_actions"]))

    def test_frozen_metrics_preserve_narrow_claim(self):
        metrics = json.loads((ROOT / "artifacts" / "evidence-gate-v1" / "metrics.json").read_text(encoding="utf-8"))
        self.assertEqual(metrics["status"], "passed_for_safety_gate_only")
        self.assertEqual(metrics["accepted_action_counts"]["ask_confirm"], 2)
        self.assertEqual(metrics["mutating_action_examples"], 0)


if __name__ == "__main__":
    unittest.main()
