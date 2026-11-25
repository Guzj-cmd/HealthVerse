from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

import joblib


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from inference import decide


VALID = {
    "source_model_status": "passed",
    "predicted_relation": "chair_sit",
    "user_available": True,
    "decision_slot": 2,
    "study_day": 10,
    "jawbone_steps_previous_30m": 0,
    "jawbone_steps_previous_60m": 30,
    "google_fit_steps_previous_30m": 0,
    "google_fit_steps_previous_60m": 20,
    "temperature_c": 22,
    "wind_speed_mph": 3,
    "precipitation_chance": 0,
    "snow_mm": 0,
    "past_suggestions_5": 2,
    "past_suggestions_20": 10,
    "recognized_activity": "STILL",
    "location_category": "work",
    "weather_condition": "Clear",
}


class HeartStepsPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifact_path = ROOT / "artifacts" / "policy-v1" / "policy.joblib"
        cls.bundle = joblib.load(cls.artifact_path)

    def test_frozen_artifact_hash(self):
        contract = json.loads((ROOT / "inference_contract.json").read_text(encoding="utf-8"))
        digest = hashlib.sha256(self.artifact_path.read_bytes()).hexdigest().upper()
        self.assertEqual(digest, contract["artifact"]["sha256"])

    def test_frozen_evaluation_passed(self):
        metrics = json.loads((ROOT / "artifacts" / "policy-v1" / "metrics.json").read_text(encoding="utf-8"))
        self.assertEqual(metrics["status"], "PASSED")
        self.assertEqual(metrics["quality_gate"]["failures"], [])
        self.assertGreater(metrics["frozen_evaluation"]["participant_cluster_bootstrap"]["ci_95"][0], 0.0)
        self.assertTrue(all(fold["participant_overlap"] == 0 for fold in metrics["folds"]))

    def test_unpassed_visual_source_requests_confirmation(self):
        decision = decide(self.bundle, {**VALID, "source_model_status": "rejected"})
        self.assertEqual(decision["immutable_action"], "ask_confirm")

    def test_transit_and_unavailable_never_suggest(self):
        transit = decide(self.bundle, {**VALID, "recognized_activity": "IN_VEHICLE"})
        unavailable = decide(self.bundle, {**VALID, "user_available": False})
        self.assertEqual(transit["immutable_action"], "no_action")
        self.assertEqual(unavailable["immutable_action"], "no_action")

    def test_valid_context_stays_in_narrow_action_contract(self):
        decision = decide(self.bundle, VALID)
        self.assertIn(decision["immutable_action"], {"no_action", "offer_activity_suggestion"})
        self.assertEqual(decision["scope"], "non_medical_activity_suggestion_only")
        self.assertIn("predicted_log_step_benefit", decision)


if __name__ == "__main__":
    unittest.main()
