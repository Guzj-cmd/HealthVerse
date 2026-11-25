import io
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audit_couch_mocap import audit_archive


def _write_sequence(bundle: zipfile.ZipFile, name: str, *, end_idx: int = 8) -> None:
    payload = io.BytesIO()
    np.savez(
        payload,
        pose=np.zeros((10, 156), dtype=np.float32),
        trans=np.zeros((10, 3), dtype=np.float32),
        R=np.eye(3, dtype=np.float32)[None],
        t=np.zeros((1, 3), dtype=np.float32),
        start_idx=np.asarray(2, dtype=np.int64),
        end_idx=np.asarray(end_idx, dtype=np.int64),
    )
    bundle.writestr(name, payload.getvalue())


def _config(archive: Path) -> dict:
    import hashlib

    return {
        "name": "test COUCH",
        "source_url": "https://example.invalid",
        "license": "test-only",
        "license_url": "https://example.invalid/license",
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "expected_subjects": ["subject1"],
        "required_arrays": ["pose", "trans", "R", "t", "start_idx", "end_idx"],
        "published_contact_taxonomy": ["right hand", "left hand"],
        "official_target_manifest": None,
        "partial_metadata_note": "test fixture has no external manifest",
        "evaluation_if_labels_become_available": "leave-one-subject-out",
        "label_policy": "explicit source target only",
    }


class CouchMocapAuditTest(unittest.TestCase):
    def test_valid_motion_without_source_target_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "mocap_npz.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                _write_sequence(
                    bundle,
                    "subject1_npz/session1_subject1_chair1_sit01_single_fitted_full.npz",
                )

            result = audit_archive(archive, _config(archive))

        self.assertEqual(result["scale"]["sequences"], 1)
        self.assertEqual(result["label_audit"]["explicit_target_sequences"], 0)
        self.assertEqual(result["quality_gate"]["status"], "blocked")
        self.assertEqual(result["evaluation"]["folds_run"], 0)

    def test_invalid_source_interval_fails_schema_check(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "mocap_npz.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                _write_sequence(
                    bundle,
                    "subject1_npz/session1_subject1_chair1_sit01_single_fitted_full.npz",
                    end_idx=11,
                )

            result = audit_archive(archive, _config(archive))

        self.assertEqual(result["scale"]["sequences"], 0)
        self.assertTrue(result["invalid_sequences"])
        self.assertFalse(
            result["quality_gate"]["checks"]["all_sequence_schemas_valid"]
        )


if __name__ == "__main__":
    unittest.main()
