import unittest

import numpy as np

from train_behave_relation_v2 import causal_mean_std, selection_key


class BehaveRelationV2Tests(unittest.TestCase):
    def test_causal_window_never_uses_future_values(self):
        values = np.asarray([[1.0], [3.0], [100.0]])
        mean, std = causal_mean_std(values, 2)
        self.assertAlmostEqual(mean[0, 0], 1.0)
        self.assertAlmostEqual(mean[1, 0], 2.0)
        self.assertAlmostEqual(std[1, 0], 1.0)
        self.assertAlmostEqual(mean[2, 0], 51.5)

    def test_selection_tie_prefers_lower_complexity_rank(self):
        result = {"aggregate": {"macro_f1": 0.9, "minimum_class_recall": 0.8, "accuracy": 0.91}}
        simpler = {"complexity_rank": 0}
        complex_model = {"complexity_rank": 3}
        self.assertGreater(selection_key(result, simpler), selection_key(result, complex_model))


if __name__ == "__main__":
    unittest.main()
