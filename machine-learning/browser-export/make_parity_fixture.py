from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import joblib


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a deterministic Python/JavaScript parity fixture.")
    parser.add_argument("--machine-learning-root", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--upper-run", required=True)
    parser.add_argument("--lower-run", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--samples", type=int, default=120)
    args = parser.parse_args()

    root = Path(args.machine_learning_root).resolve()
    sys.path.insert(0, str(root))
    from hvml.features import pose_features
    from hvml.io import load_samples

    upper_run, lower_run = Path(args.upper_run), Path(args.lower_run)
    upper = joblib.load(upper_run / "model.joblib")["model"]
    lower = joblib.load(lower_run / "model.joblib")["model"]
    with (upper_run / "splits.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        test_ids = {row["sample_id"] for row in csv.DictReader(handle) if row["split"] == "test"}

    records = []
    for sample in load_samples(args.data):
        if sample.sample_id not in test_ids:
            continue
        features = pose_features(sample.landmarks).reshape(1, -1)
        upper_probabilities = upper.predict_proba(features)[0]
        lower_probabilities = lower.predict_proba(features)[0]
        records.append({
            "sample_id": sample.sample_id,
            "landmarks": [
                {"x": float(row[0]), "y": float(row[1]), "z": float(row[2]), "visibility": float(row[3])}
                for row in sample.landmarks
            ],
            "upper": {
                "label": str(upper.classes_[int(upper_probabilities.argmax())]),
                "probabilities": [float(value) for value in upper_probabilities],
            },
            "lower": {
                "label": str(lower.classes_[int(lower_probabilities.argmax())]),
                "probabilities": [float(value) for value in lower_probabilities],
            },
        })
        if len(records) >= args.samples:
            break
    if len(records) < 100:
        raise ValueError(f"parity fixture requires at least 100 test samples, found {len(records)}")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"samples": records}, separators=(",", ":")), encoding="utf-8")
    print(f"{output} ({len(records)} samples)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
