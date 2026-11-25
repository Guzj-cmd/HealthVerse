import unittest

import numpy as np

from train_behave_relation import _common_frame_indices, _sample_indices, classify_sequence


class BehaveRelationTests(unittest.TestCase):
    def setUp(self):
        self.classes = {
            "seated_contact": ["chairblack_sit"],
            "table_lean": ["tablesmall_lean"],
            "monitor_interaction": ["monitor_hand", "monitor_move"],
        }

    def test_sequence_labels_are_exact_suffix_matches(self):
        self.assertEqual(
            classify_sequence("Date01_Sub01_chairblack_sit", self.classes, set()),
            "seated_contact",
        )
        self.assertIsNone(classify_sequence(
            "Date03_Sub03_chairblack_sitstand", self.classes, {"chairblack_sitstand"}
        ))

    def test_sampling_is_bounded_and_trimmed(self):
        selected = _sample_indices(1000, 48, 0.1)
        self.assertEqual(len(selected), 48)
        self.assertGreaterEqual(selected.min(), 100)
        self.assertLessEqual(selected.max(), 899)

    def test_frame_alignment_uses_timestamps(self):
        human = np.asarray(["t0001.000", "t0002.000", "t0003.000"])
        obj = np.asarray(["t0000.000", "t0002.000", "t0003.000"])
        human_idx, object_idx, times = _common_frame_indices(human, obj)
        self.assertEqual(times, ["t0002.000", "t0003.000"])
        np.testing.assert_array_equal(human_idx, [1, 2])
        np.testing.assert_array_equal(object_idx, [1, 2])


if __name__ == "__main__":
    unittest.main()
