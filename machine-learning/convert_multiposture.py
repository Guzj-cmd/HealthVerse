from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


LANDMARK_NAMES = (
    "nose", "left_eye_inner", "left_eye", "left_eye_outer",
    "right_eye_inner", "right_eye", "right_eye_outer", "left_ear",
    "right_ear", "mouth_left", "mouth_right", "left_shoulder",
    "right_shoulder", "left_elbow", "right_elbow", "left_wrist",
    "right_wrist", "left_pinky", "right_pinky", "left_index",
    "right_index", "left_thumb", "right_thumb", "left_hip",
    "right_hip", "left_knee", "right_knee", "left_ankle",
    "right_ankle", "left_heel", "right_heel", "left_foot_index",
    "right_foot_index",
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert the public MultiPosture CSV to HealthVerse JSONL without changing labels."
    )
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--target", choices=("upperbody_label", "lowerbody_label"), required=True
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with input_path.open("r", encoding="utf-8-sig", newline="") as source, output_path.open(
        "w", encoding="utf-8", newline=""
    ) as target:
        for index, row in enumerate(csv.DictReader(source), start=1):
            subject = str(row["subject"])
            landmarks = [
                {
                    "x": float(row[f"{name}_x"]),
                    "y": float(row[f"{name}_y"]),
                    "z": float(row[f"{name}_z"]),
                    "visibility": 1.0,
                }
                for name in LANDMARK_NAMES
            ]
            record = {
                "sample_id": f"multiposture-{index:05d}",
                "subject_id": f"subject-{subject}",
                "label": row[args.target],
                "source": "MultiPosture v1 / Zenodo 14230872",
                "landmarks": landmarks,
            }
            target.write(json.dumps(record, ensure_ascii=False) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
