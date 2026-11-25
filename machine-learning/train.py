from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from hvml.io import load_samples
from hvml.modeling import candidate_models, grouped_split, load_config, matrix, metrics, save_bundle, threshold_status


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Train and independently test the HealthVerse pose classifier.")
    parser.add_argument("--data", required=True, help="CSV or JSONL with 33 MediaPipe landmarks per sample")
    parser.add_argument("--output", required=True, help="Empty/new output directory for the run")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--dataset-manifest", help="JSON with pose_coverage measured before dropping undetected frames")
    args = parser.parse_args()

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    config, samples = load_config(args.config), load_samples(args.data)
    split_indices = grouped_split(samples, config)
    labels = sorted({sample.label for sample in samples})
    if len(labels) < 2:
        raise ValueError("at least two labels are required")

    arrays = {}
    for name, indices in split_indices.items():
        arrays[name] = matrix([samples[index] for index in indices])
        missing = sorted(set(labels) - set(arrays[name][1]))
        if missing:
            raise ValueError(f"{name} split is missing labels: {missing}; collect more subject groups")

    history, trained = [], {}
    for name, model in candidate_models(config).items():
        model.fit(*arrays["train"])
        prediction = model.predict(arrays["validation"][0])
        result = metrics(arrays["validation"][1], prediction, labels)
        history.append({"model": name, "validation": result})
        trained[name] = model
    winner = max(history, key=lambda row: (row["validation"]["macro_f1"], row["validation"]["accuracy"]))["model"]
    model = trained[winner]
    test_prediction = model.predict(arrays["test"][0])
    test_result = metrics(arrays["test"][1], test_prediction, labels)
    classifier_base, classifier_failures = threshold_status(test_result, config["thresholds"])
    test_subjects = {samples[index].subject_id for index in split_indices["test"]}
    if len(test_subjects) < int(config["thresholds"].get("minimum_test_subjects", 0)):
        classifier_failures.append("test_subject_count")
        classifier_base = "failed"
    classifier_status = "classifier_passed" if classifier_base == "passed" else "classifier_failed"
    dataset_manifest = None
    coverage_status = "pose_coverage_not_evaluated"
    if args.dataset_manifest:
        dataset_manifest = json.loads(Path(args.dataset_manifest).read_text(encoding="utf-8-sig"))
        coverage = float(dataset_manifest.get("pose_coverage", -1))
        if coverage < float(config["thresholds"].get("minimum_pose_coverage", 0)):
            coverage_status = "pose_coverage_failed"
        else:
            coverage_status = "pose_coverage_passed"
    if classifier_status == "classifier_failed" or coverage_status == "pose_coverage_failed":
        end_to_end_status = "end_to_end_failed"
    elif coverage_status == "pose_coverage_not_evaluated":
        end_to_end_status = "end_to_end_not_evaluated"
    else:
        end_to_end_status = "end_to_end_passed"
    report = {
        "status": end_to_end_status,
        "classifier_status": classifier_status,
        "classifier_failed_thresholds": classifier_failures,
        "coverage_status": coverage_status,
        "end_to_end_status": end_to_end_status,
        "selected_model": winner,
        "test": test_result,
        "thresholds": config["thresholds"],
        "split": {name: {"samples": int(len(indices)), "subjects": int(len({samples[i].subject_id for i in indices}))} for name, indices in split_indices.items()},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset": str(Path(args.data).name),
        "pose_coverage": None if dataset_manifest is None else dataset_manifest.get("pose_coverage"),
    }
    write_json(output / "metrics.json", report)
    write_json(output / "training_history.json", history)
    seen_subjects = sorted({samples[index].subject_id for name in ("train", "validation") for index in split_indices[name]})
    save_bundle(output / "model.joblib", model, labels, config, {"selected_model": winner, "classifier_status": classifier_status, "coverage_status": coverage_status, "end_to_end_status": end_to_end_status, "seen_subject_ids": seen_subjects})

    with (output / "splits.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle); writer.writerow(["sample_id", "subject_id", "label", "split"])
        for split_name, indices in split_indices.items():
            for index in indices:
                sample = samples[index]; writer.writerow([sample.sample_id, sample.subject_id, sample.label, split_name])
    with (output / "confusion_matrix.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle); writer.writerow(["actual\\predicted", *labels])
        for label, row in zip(labels, test_result["confusion_matrix"]): writer.writerow([label, *row])

    recalls = "\n".join(f"- {name}: {value:.3f}" for name, value in test_result["per_class_recall"].items())
    coverage_text = "unreported" if dataset_manifest is None else f"{float(dataset_manifest.get('pose_coverage', 0)):.4f}"
    (output / "model_card.md").write_text(f"""# HealthVerse Pose Classifier\n\n- Classifier status: **{classifier_status}**\n- Pose coverage status: **{coverage_status}**\n- End-to-end status: **{end_to_end_status}**\n- Selected estimator: `{winner}`\n- Independent test accuracy (conditional on detected pose): `{test_result['accuracy']:.4f}`\n- Independent test Macro-F1 (conditional on detected pose): `{test_result['macro_f1']:.4f}`\n- Pose coverage before filtering: `{coverage_text}`\n- Split unit: subject_id (no subject appears in more than one partition)\n\n## Per-class recall\n\n{recalls}\n\n## Intended use\n\nClassify user-defined posture states from MediaPipe 33-point landmarks. It is not a medical diagnostic model. Classifier thresholds and end-to-end pose coverage are separate claims.\n\n## Data and limitations\n\nDataset: `{Path(args.data).name}`. Review `splits.csv`, label provenance, consent, camera placement, demographics, and failure cases before deployment. Landmark-only tables cannot estimate pose detection coverage; their end-to-end status remains not evaluated.\n""", encoding="utf-8")
    print(json.dumps({"classifier_status": classifier_status, "coverage_status": coverage_status, "end_to_end_status": end_to_end_status, "selected_model": winner, "metrics": str(output / "metrics.json")}, ensure_ascii=False))
    return 0 if classifier_status == "classifier_passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
