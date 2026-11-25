from __future__ import annotations

import unittest
import warnings

import numpy as np
from sklearn.exceptions import ConvergenceWarning

from hvml.features import feature_names, pose_features
from hvml.datasets import DatasetSpec, load_mapped_samples, merge_mapped_datasets
from hvml.io import PoseSample, write_jsonl_sample
from hvml.modeling import candidate_models, grouped_split, leave_one_dataset_out_split, threshold_status


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

    def test_leave_one_dataset_out_keeps_holdout_intact(self):
        landmarks = np.zeros((33, 4)); landmarks[:, 3] = 1
        samples = [
            PoseSample(f"a-{g}-{i}", f"person-{g}", "upright", "a", landmarks, "dataset-a")
            for g in range(4) for i in range(2)
        ] + [
            PoseSample(f"b-{g}-{i}", f"person-{g}", "upright", "b", landmarks, "dataset-b")
            for g in range(3) for i in range(2)
        ]
        config = {"random_seed": 7, "split": {"validation_fraction": .25}}
        split = leave_one_dataset_out_split(samples, "dataset-b", config)
        self.assertEqual({samples[i].dataset_id for i in split["test"]}, {"dataset-b"})
        self.assertEqual({samples[i].dataset_id for i in split["train"]}, {"dataset-a"})
        self.assertEqual({samples[i].dataset_id for i in split["validation"]}, {"dataset-a"})
        development_subjects = {
            samples[i].subject_id for name in ("train", "validation") for i in split[name]
        }
        test_subjects = {samples[i].subject_id for i in split["test"]}
        # Raw names may collide across datasets; dataset holdout remains intact.
        self.assertTrue(development_subjects & test_subjects)

    def test_dataset_mapping_is_explicit_and_namespaced(self):
        import tempfile
        from pathlib import Path

        landmarks = np.zeros((33, 4)); landmarks[:, 3] = 1
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.jsonl"
            second = Path(directory) / "second.jsonl"
            for path, label in ((first, "neutral"), (second, "forward")):
                with path.open("w", encoding="utf-8") as handle:
                    write_jsonl_sample(handle, PoseSample("1", "person-1", label, "capture", landmarks))
            spec_a = DatasetSpec("dataset-a", {"neutral": "TUP"})
            spec_b = DatasetSpec("dataset-b", {"forward": "TLF"})
            merged = merge_mapped_datasets([(first, spec_a), (second, spec_b)])
            self.assertEqual({sample.sample_id for sample in merged}, {"dataset-a:1", "dataset-b:1"})
            self.assertEqual({sample.subject_id for sample in merged}, {"dataset-a:person-1", "dataset-b:person-1"})
            self.assertEqual({sample.label for sample in merged}, {"TUP", "TLF"})
            with self.assertRaisesRegex(ValueError, "unmapped label"):
                load_mapped_samples(first, DatasetSpec("bad-map", {"other": "TUP"}))

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
