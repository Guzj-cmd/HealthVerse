from __future__ import annotations

import unittest
import warnings

import numpy as np
from sklearn.exceptions import ConvergenceWarning

from hvml.features import feature_names, pose_features
from hvml.io import PoseSample
from hvml.modeling import candidate_models, grouped_split, threshold_status


class PipelineTests(unittest.TestCase):
    def test_feature_shape_and_finiteness(self):
        rng = np.random.default_rng(1)
        landmarks = rng.normal(size=(33, 4)); landmarks[:, 3] = 0.9
        vector = pose_features(landmarks)
        self.assertEqual(vector.shape, (len(feature_names()),))
        self.assertTrue(np.isfinite(vector).all())

    def test_subject_groups_never_leak(self):
        landmarks = np.zeros((33, 4)); landmarks[:, 3] = 1
        samples = [PoseSample(f"s{g}-{i}", f"person-{g}", "upright" if i % 2 else "forward", "test", landmarks) for g in range(10) for i in range(4)]
        config = {"random_seed": 42, "split": {"train_fraction": .7, "validation_fraction": .15, "test_fraction": .15}}
        indices = grouped_split(samples, config)
        groups = {name: {samples[i].subject_id for i in values} for name, values in indices.items()}
        self.assertFalse(groups["train"] & groups["validation"])
        self.assertFalse(groups["train"] & groups["test"])
        self.assertFalse(groups["validation"] & groups["test"])

    def test_threshold_requires_every_class(self):
        result = {"accuracy": .91, "macro_f1": .86, "per_class_recall": {"upright": .88, "forward": .62}, "class_support": {"upright": 50, "forward": 50}}
        status, failures = threshold_status(result, {"accuracy": .85, "macro_f1": .8, "minimum_class_recall": .7})
        self.assertEqual(status, "failed")
        self.assertIn("class_recall:forward", failures)

    def test_small_test_set_cannot_pass(self):
        result = {"accuracy": .95, "macro_f1": .94, "per_class_recall": {"upright": .95, "forward": .93}, "class_support": {"upright": 20, "forward": 7}}
        status, failures = threshold_status(result, {"accuracy": .85, "macro_f1": .8, "minimum_class_recall": .7, "minimum_test_samples_per_class": 30})
        self.assertEqual(status, "failed")
        self.assertTrue(any(item.startswith("class_support:") for item in failures))

    def test_every_candidate_estimator_fits(self):
        rng = np.random.default_rng(3)
        x = rng.normal(size=(48, len(feature_names())))
        y = np.asarray(["upright", "forward"] * 24)
        config = {
            "random_seed": 42,
            "models": {
                "logistic_regression": {"C": 1.0, "max_iter": 100},
                "random_forest": {"n_estimators": 8, "max_depth": 4, "min_samples_leaf": 1},
                "hist_gradient_boosting": {"max_iter": 8, "learning_rate": .1, "max_leaf_nodes": 7},
                "edusense_mlp": {"hidden_layer_sizes": [8], "alpha": .001, "max_iter": 30},
            },
        }
        for model in candidate_models(config).values():
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", ConvergenceWarning)
                model.fit(x, y)
            self.assertEqual(model.predict(x[:3]).shape, (3,))


if __name__ == "__main__":
    unittest.main()
