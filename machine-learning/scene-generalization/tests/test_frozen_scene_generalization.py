from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts" / "scene-specialist-v1"


class FrozenSceneGeneralizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = json.loads((ARTIFACT / "baseline_metrics.json").read_text(encoding="utf-8"))
        cls.candidate = json.loads((ARTIFACT / "metrics.json").read_text(encoding="utf-8"))

    def test_official_test_split_was_not_used(self):
        self.assertIn("official test not loaded", self.candidate["source_split"])
        self.assertIn("official test not loaded", self.baseline["protocol"]["source_split"])

    def test_joint_scene_and_subject_holdout(self):
        self.assertEqual(len(self.candidate["folds"]), 5)
        self.assertTrue(all(fold["subject_overlap"] == 0 for fold in self.candidate["folds"]))

    def test_frozen_gate_passes_without_target_weighting(self):
        gate = self.candidate["quality_gate"]
        self.assertEqual(gate["status"], "PASSED")
        self.assertEqual(gate["failures"], [])
        self.assertIn("target labels do not participate", self.candidate["weight_contract"])
        self.assertGreaterEqual(
            self.candidate["aggregate"]["macro_map_supported"],
            gate["thresholds"]["minimum_aggregate_macro_map"],
        )
        for fold in self.candidate["folds"]:
            self.assertGreaterEqual(
                fold["metrics"]["macro_map_supported"],
                gate["thresholds"]["minimum_each_scene_macro_map_supported"],
            )
            self.assertGreaterEqual(
                fold["metrics"]["supported_classes"],
                gate["thresholds"]["minimum_supported_classes_per_scene"],
            )

    def test_candidate_improves_frozen_baseline(self):
        comparison = self.candidate["comparison"]
        self.assertAlmostEqual(
            comparison["baseline_macro_map"], self.baseline["aggregate"]["macro_map_supported"], places=12
        )
        self.assertGreater(comparison["candidate_macro_map"], comparison["baseline_macro_map"])


if __name__ == "__main__":
    unittest.main()
