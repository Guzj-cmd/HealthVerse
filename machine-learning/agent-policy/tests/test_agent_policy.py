from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from policy import conservative_select


class AgentPolicyAuditTests(unittest.TestCase):
    def test_untrained_policy_never_acts(self):
        decision = conservative_select("untrained", [("raise_monitor", 0.99)], {})
        self.assertEqual(decision.action, "ask_confirm")

    def test_safety_layer_is_after_policy(self):
        decision = conservative_select("passed", [("raise_monitor", 0.95)], {"lock_monitor": True})
        self.assertEqual(decision.action, "ask_confirm")
        self.assertIn("constraint:lock_monitor", decision.rationale_codes)

    def test_teacher_v2_uses_real_contexts_and_no_missing_environment_action(self):
        teacher = json.loads((ROOT / "artifacts" / "teacher-v2" / "labels.json").read_text(encoding="utf-8"))
        self.assertEqual(teacher["source"], "real_MultiPosture_observations")
        self.assertGreaterEqual(teacher["coverage"], 0.60)
        for item in teacher["consensus"]:
            self.assertEqual(item["context"]["environment_fields"], "unavailable")
            self.assertNotIn(item["teacher_label"]["recommended_action"], {"raise_monitor", "reposition_object", "take_break"})

    def test_student_gate_and_subject_isolation(self):
        metrics = json.loads((ROOT / "artifacts" / "student-v2" / "metrics.json").read_text(encoding="utf-8"))
        self.assertEqual(metrics["status"], "passed")
        self.assertEqual(metrics["metric_semantics"], "agreement with filtered AI-teacher labels, not medical or ergonomic correctness")
        splits = [set(metrics["split"][name]["subjects"]) for name in ("train", "validation", "test")]
        self.assertFalse(splits[0] & splits[1] or splits[0] & splits[2] or splits[1] & splits[2])


if __name__ == "__main__":
    unittest.main()
