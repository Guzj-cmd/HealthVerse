from __future__ import annotations

import argparse
import json

import joblib

from hvml.io import load_samples
from hvml.modeling import matrix, metrics, threshold_status


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate an exported HealthVerse model on a separate labeled dataset.")
    parser.add_argument("--model", required=True)
    parser.add_argument("--data", required=True)
    args = parser.parse_args()
    bundle = joblib.load(args.model)
    samples = load_samples(args.data)
    overlap = sorted(set(bundle.get("metadata", {}).get("seen_subject_ids", [])) & {sample.subject_id for sample in samples})
    if overlap:
        raise ValueError("external evaluation contains subjects seen during development: " + ", ".join(overlap))
    x, y = matrix(samples)
    result = metrics(y, bundle["model"].predict(x), bundle["labels"])
    status, failures = threshold_status(result, bundle["config"]["thresholds"])
    subject_count = len({sample.subject_id for sample in samples})
    if subject_count < int(bundle["config"]["thresholds"].get("minimum_test_subjects", 0)):
        failures.append("test_subject_count")
        status = "failed"
    classifier_status = "classifier_passed" if status == "passed" else "classifier_failed"
    print(json.dumps({"classifier_status": classifier_status, "coverage_status": "pose_coverage_not_evaluated", "end_to_end_status": "end_to_end_not_evaluated" if classifier_status == "classifier_passed" else "end_to_end_failed", "classifier_failed_thresholds": failures, "subject_count": subject_count, "metrics": result}, ensure_ascii=False, indent=2))
    return 0 if status == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
