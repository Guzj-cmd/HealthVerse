import io
import tarfile
import tempfile
import unittest
from pathlib import Path

import numpy as np

from train_charades_relation import (
    AnnotationTable,
    choose_thresholds,
    expected_calibration_error,
    gate_failures,
    load_feature_cache,
    parse_action_ids,
    pool_official_fc7_archive,
    relation_vector,
    validate_official_split,
)


class CharadesRelationTests(unittest.TestCase):
    def test_relation_mapping_is_multilabel(self):
        relations = {
            "chair": ["c059"],
            "laptop": ["c051", "c052"],
        }
        actions = parse_action_ids("c059 1.00 2.00;c052 3.00 4.00")
        np.testing.assert_array_equal(relation_vector(actions, relations), [1, 1])

    def test_official_split_rejects_subject_overlap(self):
        table = AnnotationTable(
            ids=np.asarray(["A"]),
            subjects=np.asarray(["S1"]),
            labels=np.asarray([[1]], dtype=np.int8),
            scenes=np.asarray(["Office"]),
        )
        other = AnnotationTable(
            ids=np.asarray(["B"]),
            subjects=np.asarray(["S1"]),
            labels=np.asarray([[0]], dtype=np.int8),
            scenes=np.asarray(["Kitchen"]),
        )
        with self.assertRaisesRegex(ValueError, "subject IDs"):
            validate_official_split(table, other)

    def test_streaming_pool_uses_mean_and_max(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "features.tar.gz"
            vectors = [np.ones(4096, dtype=np.float32), np.full(4096, 3.0, dtype=np.float32)]
            with tarfile.open(archive, "w:gz") as tar:
                for frame, vector in enumerate(vectors, start=1):
                    payload = " ".join(str(value) for value in vector).encode("ascii")
                    info = tarfile.TarInfo(
                        f"Charades_v1_features_rgb/ABCDE/ABCDE-{frame:06d}.txt"
                    )
                    info.size = len(payload)
                    tar.addfile(info, io.BytesIO(payload))
            output = root / "pooled.npz"
            record = pool_official_fc7_archive(archive, output, frame_stride=1)
            ids, features = load_feature_cache(output)
            self.assertEqual(record["archive_frames"], 2)
            self.assertEqual(record["pooled_frames"], 2)
            self.assertEqual(ids.tolist(), ["ABCDE"])
            np.testing.assert_allclose(features[0, :4096], 2.0)
            np.testing.assert_allclose(features[0, 4096:], 3.0)

    def test_thresholds_and_gate_are_train_derived_and_explicit(self):
        y = np.asarray([[0], [0], [1], [1]], dtype=np.int8)
        p = np.asarray([[0.1], [0.2], [0.7], [0.8]])
        threshold = choose_thresholds(y, p)
        self.assertGreaterEqual(threshold[0], 0.2)
        self.assertLessEqual(threshold[0], 0.7)
        self.assertLess(expected_calibration_error(y, p), 0.3)
        metrics = {
            "macro_map": 0.9,
            "macro_f1": 0.8,
            "per_class_ap": {"chair": 0.9},
            "per_class_recall": {"chair": 0.7},
            "prevalence": {"chair": 0.2},
        }
        gate = {
            "minimum_macro_map": 0.35,
            "minimum_macro_f1": 0.35,
            "minimum_ap_above_prevalence": 0.1,
            "minimum_class_recall": 0.5,
        }
        self.assertEqual(gate_failures(metrics, gate), [])


if __name__ == "__main__":
    unittest.main()
