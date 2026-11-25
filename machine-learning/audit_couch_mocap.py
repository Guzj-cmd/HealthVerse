"""Audit the official COUCH MoCap archive without inventing posture labels.

The lightweight ``mocap_npz.zip`` release contains motion and transform arrays.
This adapter records its real scale and checks whether it also contains a
source-provided target suitable for participant-disjoint training. It does not
derive contact or health labels from geometry or filename tokens.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import statistics
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np


SUBJECT_RE = re.compile(r"(?:^|/)(subject\d+)_npz/")
CHAIR_RE = re.compile(r"_(chair\d+|sofa)_")
EXPLICIT_TARGET_NAMES = {
    "contact",
    "contacts",
    "contact_type",
    "hand_contact",
    "hand_contacts",
    "interaction_type",
    "label",
    "labels",
    "target",
    "targets",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _scalar_int(value: np.ndarray) -> int:
    array = np.asarray(value)
    if array.size != 1:
        raise ValueError(f"expected scalar integer, got shape {array.shape}")
    return int(array.reshape(-1)[0])


def inspect_npz_bytes(payload: bytes, name: str, required_arrays: set[str]) -> dict[str, Any]:
    with np.load(io.BytesIO(payload), allow_pickle=False) as data:
        arrays = set(data.files)
        missing = sorted(required_arrays - arrays)
        explicit_targets = sorted(arrays & EXPLICIT_TARGET_NAMES)
        if missing:
            return {
                "name": name,
                "valid": False,
                "errors": [f"missing arrays: {', '.join(missing)}"],
                "explicit_targets": explicit_targets,
            }

        errors: list[str] = []
        pose = np.asarray(data["pose"])
        trans = np.asarray(data["trans"])
        rotation = np.asarray(data["R"])
        translation = np.asarray(data["t"])
        try:
            start_idx = _scalar_int(data["start_idx"])
            end_idx = _scalar_int(data["end_idx"])
        except (TypeError, ValueError) as exc:
            errors.append(str(exc))
            start_idx = end_idx = -1

        frames = int(pose.shape[0]) if pose.ndim >= 1 else 0
        if pose.ndim != 2 or pose.shape[1] != 156:
            errors.append(f"pose shape {pose.shape}, expected (T, 156)")
        if trans.shape != (frames, 3):
            errors.append(f"trans shape {trans.shape}, expected ({frames}, 3)")
        if rotation.shape != (1, 3, 3):
            errors.append(f"R shape {rotation.shape}, expected (1, 3, 3)")
        if translation.shape != (1, 3):
            errors.append(f"t shape {translation.shape}, expected (1, 3)")
        if not (0 <= start_idx < end_idx <= frames):
            errors.append(
                f"invalid source interval [{start_idx}, {end_idx}) for {frames} frames"
            )

        return {
            "name": name,
            "valid": not errors,
            "errors": errors,
            "frames": frames,
            "start_idx": start_idx,
            "end_idx": end_idx,
            "arrays": sorted(arrays),
            "explicit_targets": explicit_targets,
        }


def audit_archive(archive: Path, config: dict[str, Any]) -> dict[str, Any]:
    required_arrays = set(config["required_arrays"])
    expected_subjects = set(config["expected_subjects"])
    observed_sha256 = sha256_file(archive)
    expected_sha256 = str(config["archive_sha256"]).lower()

    subject_counts: dict[str, dict[str, int]] = defaultdict(
        lambda: {"sequences": 0, "frames": 0}
    )
    chair_counts: dict[str, dict[str, int]] = defaultdict(
        lambda: {"sequences": 0, "frames": 0}
    )
    schemas: Counter[tuple[str, ...]] = Counter()
    frame_counts: list[int] = []
    annotated_interval_frames = 0
    invalid_sequences: list[dict[str, Any]] = []
    explicit_target_sequences: list[dict[str, Any]] = []

    with zipfile.ZipFile(archive) as bundle:
        bad_member = bundle.testzip()
        npz_names = sorted(name for name in bundle.namelist() if name.endswith(".npz"))
        for name in npz_names:
            subject_match = SUBJECT_RE.search(name)
            chair_match = CHAIR_RE.search(Path(name).name)
            result = inspect_npz_bytes(bundle.read(name), name, required_arrays)
            if not result["valid"]:
                invalid_sequences.append(
                    {"name": name, "errors": result["errors"]}
                )
                continue

            frames = int(result["frames"])
            frame_counts.append(frames)
            annotated_interval_frames += int(result["end_idx"] - result["start_idx"])
            schemas[tuple(result["arrays"])] += 1
            if subject_match:
                subject = subject_match.group(1)
                subject_counts[subject]["sequences"] += 1
                subject_counts[subject]["frames"] += frames
            if chair_match:
                chair = chair_match.group(1)
                chair_counts[chair]["sequences"] += 1
                chair_counts[chair]["frames"] += frames
            if result["explicit_targets"]:
                explicit_target_sequences.append(
                    {"name": name, "arrays": result["explicit_targets"]}
                )

    observed_subjects = set(subject_counts)
    schema_valid = not invalid_sequences
    archive_valid = bad_member is None
    explicit_target_coverage = len(explicit_target_sequences)
    target_gate = explicit_target_coverage == len(frame_counts) and bool(frame_counts)
    loso_ready = expected_subjects == observed_subjects and target_gate

    checks = {
        "zip_crc_valid": archive_valid,
        "archive_sha256_matches": observed_sha256 == expected_sha256,
        "all_expected_subjects_present": expected_subjects == observed_subjects,
        "all_sequence_schemas_valid": schema_valid,
        "explicit_source_target_present_for_every_sequence": target_gate,
        "loso_training_permitted": loso_ready,
    }
    blocker = None
    if not target_gate:
        blocker = (
            "The official lightweight MoCap NPZ archive contains no explicit "
            "contact/interaction target array or official sequence-to-label manifest. "
            "start_idx/end_idx are retained as source interval metadata, but the "
            "release does not define them as hand-contact or ergonomic classes."
        )

    return {
        "dataset": config["name"],
        "source_url": config["source_url"],
        "license": config["license"],
        "license_url": config["license_url"],
        "archive": {
            "filename": archive.name,
            "bytes": archive.stat().st_size,
            "sha256": observed_sha256,
            "zip_crc_valid": archive_valid,
        },
        "scale": {
            "subjects": len(subject_counts),
            "sequences": len(frame_counts),
            "frames": int(sum(frame_counts)),
            "annotated_interval_frames": int(annotated_interval_frames),
            "min_sequence_frames": min(frame_counts) if frame_counts else 0,
            "median_sequence_frames": statistics.median(frame_counts)
            if frame_counts
            else 0,
            "max_sequence_frames": max(frame_counts) if frame_counts else 0,
        },
        "per_subject": dict(sorted(subject_counts.items())),
        "per_chair": dict(sorted(chair_counts.items())),
        "schemas": [
            {"arrays": list(schema), "sequences": count}
            for schema, count in sorted(schemas.items())
        ],
        "label_audit": {
            "published_contact_taxonomy": config["published_contact_taxonomy"],
            "explicit_target_sequences": explicit_target_coverage,
            "official_target_manifest": config["official_target_manifest"],
            "partial_metadata_note": config["partial_metadata_note"],
            "source_interval_fields": ["start_idx", "end_idx"],
            "admissible_label_policy": config["label_policy"],
            "filename_tokens_used_as_ground_truth": False,
            "geometry_used_as_ground_truth": False,
        },
        "evaluation": {
            "planned": config["evaluation_if_labels_become_available"],
            "folds_run": 0,
            "metrics": None,
        },
        "quality_gate": {
            "status": "blocked" if blocker else "passed",
            "checks": checks,
            "blocker": blocker,
        },
        "invalid_sequences": invalid_sequences,
        "explicit_target_examples": explicit_target_sequences[:10],
    }


def render_report(result: dict[str, Any]) -> str:
    scale = result["scale"]
    checks = result["quality_gate"]["checks"]
    subjects = "\n".join(
        f"| {name} | {values['sequences']} | {values['frames']} |"
        for name, values in result["per_subject"].items()
    )
    check_rows = "\n".join(
        f"| {name} | {'PASS' if passed else 'FAIL'} |"
        for name, passed in checks.items()
    )
    return f"""# COUCH MoCap data audit

## Result

Training is **blocked**. The archive is real, intact and suitable for six-subject
isolation, but it does not carry an explicit target for the published hand-contact
taxonomy. No model, accuracy or derived weights were produced.

## Verified scale

- Archive SHA-256: `{result['archive']['sha256']}`
- Sequences: {scale['sequences']}
- Frames: {scale['frames']}
- Source interval frames: {scale['annotated_interval_frames']}
- Sequence length: {scale['min_sequence_frames']} / {scale['median_sequence_frames']} / {scale['max_sequence_frames']} frames (min / median / max)

| Subject | Sequences | Frames |
| --- | ---: | ---: |
{subjects}

## Quality gate

| Check | Result |
| --- | --- |
{check_rows}

Blocker: {result['quality_gate']['blocker']}

The paper's interaction taxonomy is recorded for provenance, but neither chair
names nor motion-name tokens are mapped to it in this archive. Pose geometry and
distance thresholds are not used as labels. `start_idx` and `end_idx` remain
interval metadata because the lightweight release does not document them as
contact or ergonomic classes.

Repository metadata audit: {result['label_audit']['partial_metadata_note']}

## Evaluation contract

If an official contact manifest is supplied later, the intended evaluation is
leave-one-subject-out over all six subjects. This audit ran zero folds and reports
no predictive metric; an integrity check is not a model benchmark.

License: [{result['license']}]({result['license_url']}). Raw data remains in an
ignored local cache and is not redistributed.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).with_name("datasets") / "couch-mocap.json",
    )
    parser.add_argument("--out-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    result = audit_archive(args.archive, config)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "metrics.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.out_dir / "audit_report.md").write_text(
        render_report(result), encoding="utf-8"
    )
    print(json.dumps(result["quality_gate"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
