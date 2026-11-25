from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import accuracy_score, f1_score, recall_score
from sklearn.model_selection import GroupKFold

from hvml.io import PoseSample, load_samples
from hvml.modeling import candidate_models, load_config, matrix, metrics, threshold_status


def fixed_metrics(y_true: np.ndarray, y_pred: np.ndarray, labels: list[str]) -> dict[str, float]:
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
        "balanced_accuracy": float(recall_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
    }


def cluster_bootstrap(y_true: np.ndarray, y_pred: np.ndarray, groups: np.ndarray, labels: list[str], repeats: int, seed: int) -> dict:
    unique_groups = np.unique(groups)
    if unique_groups.size < 2:
        raise ValueError("cluster bootstrap requires at least two held-out subjects")
    group_indices = {group: np.flatnonzero(groups == group) for group in unique_groups}
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(repeats):
        sampled = rng.choice(unique_groups, size=unique_groups.size, replace=True)
        indices = np.concatenate([group_indices[group] for group in sampled])
        rows.append(fixed_metrics(y_true[indices], y_pred[indices], labels))
    result = {"method": "subject_cluster_bootstrap", "repeats": repeats, "cluster_count": int(unique_groups.size), "confidence_level": 0.95, "metrics": {}}
    for name in ("accuracy", "macro_f1", "balanced_accuracy"):
        values = np.asarray([row[name] for row in rows])
        result["metrics"][name] = {
            "point": fixed_metrics(y_true, y_pred, labels)[name],
            "ci_low": float(np.quantile(values, .025)),
            "ci_high": float(np.quantile(values, .975)),
        }
    return result


def heldout_predictions(data_path: Path, run_path: Path) -> tuple[list[PoseSample], np.ndarray, np.ndarray, np.ndarray, list[str], str]:
    samples = load_samples(data_path)
    split_rows = list(csv.DictReader((run_path / "splits.csv").open("r", encoding="utf-8-sig", newline="")))
    test_ids = {row["sample_id"] for row in split_rows if row["split"] == "test"}
    test_samples = [sample for sample in samples if sample.sample_id in test_ids]
    if len(test_samples) != len(test_ids):
        raise ValueError(f"split/data mismatch in {run_path}")
    x, y = matrix(test_samples)
    bundle = joblib.load(run_path / "model.joblib")
    prediction = bundle["model"].predict(x)
    groups = np.asarray([sample.subject_id for sample in test_samples])
    return test_samples, y, prediction, groups, list(bundle["labels"]), str(bundle["metadata"]["selected_model"])


def group_k_fold(data_path: Path, config: dict, model_name: str, labels: list[str], requested_folds: int) -> tuple[list[dict], dict]:
    samples = load_samples(data_path)
    x, y = matrix(samples)
    groups = np.asarray([sample.subject_id for sample in samples])
    split_count = min(requested_folds, len(np.unique(groups)))
    if split_count < 2:
        raise ValueError("GroupKFold requires at least two subjects")
    rows, pooled_true, pooled_pred = [], [], []
    splitter = GroupKFold(n_splits=split_count)
    for fold_id, (train_index, test_index) in enumerate(splitter.split(x, y, groups), start=1):
        model = candidate_models(config)[model_name]
        model.fit(x[train_index], y[train_index])
        prediction = model.predict(x[test_index])
        score = fixed_metrics(y[test_index], prediction, labels)
        per_class = recall_score(y[test_index], prediction, labels=labels, average=None, zero_division=0)
        test_subjects = sorted(str(value) for value in np.unique(groups[test_index]))
        row = {
            "fold": fold_id, "test_subjects": "|".join(test_subjects), "test_subject_count": len(test_subjects),
            "train_samples": int(train_index.size), "test_samples": int(test_index.size),
            **score, "minimum_class_recall": float(np.min(per_class)),
        }
        rows.append(row); pooled_true.append(y[test_index]); pooled_pred.append(prediction)
    all_true, all_pred = np.concatenate(pooled_true), np.concatenate(pooled_pred)
    pooled = fixed_metrics(all_true, all_pred, labels)
    worst = min(rows, key=lambda item: (item["macro_f1"], item["balanced_accuracy"], item["accuracy"]))
    return rows, {
        "method": "group_k_fold", "group_field": "subject_id", "folds": len(rows),
        "pooled": pooled,
        "mean": {name: float(np.mean([row[name] for row in rows])) for name in ("accuracy", "macro_f1", "balanced_accuracy")},
        "worst_unseen_subject_group": worst,
    }


def classifier_status(test_result: dict, test_subject_count: int, thresholds: dict) -> tuple[str, list[str]]:
    base, failures = threshold_status(test_result, thresholds)
    if test_subject_count < int(thresholds.get("minimum_test_subjects", 0)):
        failures.append("test_subject_count"); base = "failed"
    return ("classifier_passed" if base == "passed" else "classifier_failed"), failures


def analyze_task(name: str, data: Path, run: Path, config: dict, repeats: int, seed: int, cv_folds: int) -> tuple[dict, list[dict]]:
    test_samples, y, prediction, groups, labels, model_name = heldout_predictions(data, run)
    detailed = metrics(y, prediction, labels)
    status, failures = classifier_status(detailed, len(np.unique(groups)), config["thresholds"])
    bootstrap = cluster_bootstrap(y, prediction, groups, labels, repeats, seed)
    folds, cv_summary = group_k_fold(data, config, model_name, labels, cv_folds)
    return {
        "task": name, "dataset": data.name, "saved_run": run.name, "fixed_model_family": model_name,
        "classifier_status": status, "classifier_failed_thresholds": failures,
        "coverage_status": "pose_coverage_not_evaluated",
        "end_to_end_status": "end_to_end_not_evaluated",
        "coverage_note": "MultiPosture is a landmark-only table containing successful landmark records; source-frame pose coverage cannot be reconstructed and is N/A.",
        "heldout_test": {**fixed_metrics(y, prediction, labels), "subjects": int(len(np.unique(groups))), "samples": int(len(y))},
        "subject_cluster_bootstrap_95_ci": bootstrap,
        "group_k_fold": cv_summary,
    }, [{"task": name, **row} for row in folds]


def main() -> int:
    parser = argparse.ArgumentParser(description="Subject-cluster bootstrap and GroupKFold robustness analysis for MultiPosture.")
    parser.add_argument("--upper-data", required=True); parser.add_argument("--upper-run", required=True)
    parser.add_argument("--lower-data", required=True); parser.add_argument("--lower-run", required=True)
    parser.add_argument("--config", required=True); parser.add_argument("--output", required=True)
    parser.add_argument("--bootstrap-repeats", type=int, default=2000); parser.add_argument("--seed", type=int, default=20261125)
    parser.add_argument("--cv-folds", type=int, default=5)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("output directory must be new or empty; existing runs are never overwritten")
    output.mkdir(parents=True, exist_ok=True)
    config = load_config(args.config)
    upper, upper_folds = analyze_task("upper_body", Path(args.upper_data), Path(args.upper_run), config, args.bootstrap_repeats, args.seed, args.cv_folds)
    lower, lower_folds = analyze_task("lower_body", Path(args.lower_data), Path(args.lower_run), config, args.bootstrap_repeats, args.seed + 1, args.cv_folds)
    report = {
        "schema": "healthverse.robustness.v1", "created_at": datetime.now(timezone.utc).isoformat(),
        "bootstrap_unit": "subject_id", "frame_bootstrap_forbidden": True,
        "coverage_status": "pose_coverage_not_evaluated", "end_to_end_status": "end_to_end_not_evaluated",
        "tasks": [upper, lower],
    }
    (output / "robustness.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    with (output / "groupkfold_folds.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = ["task", "fold", "test_subjects", "test_subject_count", "train_samples", "test_samples", "accuracy", "macro_f1", "balanced_accuracy", "minimum_class_recall"]
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(upper_folds + lower_folds)
    with (output / "cluster_bootstrap_ci.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle); writer.writerow(["task", "metric", "point", "ci_low", "ci_high", "clusters", "repeats"])
        for task in (upper, lower):
            boot = task["subject_cluster_bootstrap_95_ci"]
            for metric_name, value in boot["metrics"].items():
                writer.writerow([task["task"], metric_name, value["point"], value["ci_low"], value["ci_high"], boot["cluster_count"], boot["repeats"]])
    lines = ["# MultiPosture Robustness Analysis", "", "All uncertainty resampling is clustered by `subject_id`; frames are never bootstrapped independently.", "", "## Coverage boundary", "", "MultiPosture contains landmark rows after successful extraction, not the original stream with failed detections. Pose coverage is therefore **N/A**, and the end-to-end status is **not evaluated**.", ""]
    for task in (upper, lower):
        boot = task["subject_cluster_bootstrap_95_ci"]["metrics"]
        worst = task["group_k_fold"]["worst_unseen_subject_group"]
        lines += [f"## {task['task']}", "", f"- Classifier status: `{task['classifier_status']}`", f"- End-to-end status: `{task['end_to_end_status']}`", f"- Fixed estimator for GroupKFold: `{task['fixed_model_family']}`", f"- Held-out Accuracy: {boot['accuracy']['point']:.4f} (subject-cluster 95% CI {boot['accuracy']['ci_low']:.4f}–{boot['accuracy']['ci_high']:.4f})", f"- Held-out Macro-F1: {boot['macro_f1']['point']:.4f} (95% CI {boot['macro_f1']['ci_low']:.4f}–{boot['macro_f1']['ci_high']:.4f})", f"- Held-out Balanced Accuracy: {boot['balanced_accuracy']['point']:.4f} (95% CI {boot['balanced_accuracy']['ci_low']:.4f}–{boot['balanced_accuracy']['ci_high']:.4f})", f"- GroupKFold pooled Macro-F1: {task['group_k_fold']['pooled']['macro_f1']:.4f}", f"- Worst unseen subject group: `{worst['test_subjects']}`; Macro-F1 {worst['macro_f1']:.4f}; Balanced Accuracy {worst['balanced_accuracy']:.4f}", ""]
    lines += ["## Interpretation", "", "These results measure classification conditional on an available 33-point landmark record. They do not establish camera-stream coverage, clinical validity, or performance on a new camera/domain."]
    (output / "ROBUSTNESS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "tasks": [upper["task"], lower["task"]], "end_to_end_status": "end_to_end_not_evaluated"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
