from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import joblib


def compact_float(value: float) -> float:
    return float(f"{float(value):.12g}")


def export_hist_gradient_boosting(model) -> dict:
    trees = []
    for iteration in model._predictors:
        class_trees = []
        for predictor in iteration:
            nodes = predictor.nodes
            class_trees.append([
                [
                    int(node["feature_idx"]),
                    compact_float(node["num_threshold"]),
                    int(node["left"]),
                    int(node["right"]),
                    compact_float(node["value"]),
                    int(node["missing_go_to_left"]),
                    int(node["is_leaf"]),
                ]
                for node in nodes
            ])
        trees.append(class_trees)
    return {
        "type": "hist_gradient_boosting_classifier",
        "classes": [str(value) for value in model.classes_],
        "baseline": [compact_float(value) for value in model._baseline_prediction.reshape(-1)],
        "trees": trees,
    }


def export_random_forest(model) -> dict:
    trees = []
    for estimator in model.estimators_:
        tree = estimator.tree_
        nodes = []
        for index in range(tree.node_count):
            values = tree.value[index][0]
            total = float(values.sum())
            probabilities = [compact_float(value / total) if total else 0.0 for value in values]
            nodes.append([
                int(tree.feature[index]),
                compact_float(tree.threshold[index]),
                int(tree.children_left[index]),
                int(tree.children_right[index]),
                probabilities,
            ])
        trees.append(nodes)
    return {
        "type": "random_forest_classifier",
        "classes": [str(value) for value in model.classes_],
        "trees": trees,
    }


def load_run(run_path: Path) -> tuple[dict, dict, dict]:
    bundle = joblib.load(run_path / "model.joblib")
    metrics = json.loads((run_path / "metrics.json").read_text(encoding="utf-8"))
    model = bundle["model"]
    if model.__class__.__name__ == "HistGradientBoostingClassifier":
        portable = export_hist_gradient_boosting(model)
    elif model.__class__.__name__ in {"RandomForestClassifier", "ExtraTreesClassifier"}:
        portable = export_random_forest(model)
    else:
        raise TypeError(f"unsupported browser export estimator: {model.__class__.__name__}")
    metric_status = metrics.get("status") or metrics.get("experiment_status")
    split = metrics["split"]
    test_subjects = split.get("test_subjects") or split.get("test", {}).get("subjects", [])
    if isinstance(test_subjects, int):
        with (run_path / "splits.csv").open("r", encoding="utf-8-sig", newline="") as handle:
            test_subjects = sorted({
                row["subject_id"] for row in csv.DictReader(handle) if row["split"] == "test"
            })
    evaluation = {
        "status": metric_status,
        "selected_model": metrics["selected_model"],
        "accuracy": metrics["test"]["accuracy"],
        "macro_f1": metrics["test"]["macro_f1"],
        "per_class_recall": metrics["test"]["per_class_recall"],
        "test_samples": metrics["test"]["sample_count"],
        "test_subjects": test_subjects,
        "split_unit": "subject_id",
        "dataset": metrics["dataset"],
    }
    return portable, evaluation, bundle["feature_schema"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Export passed sklearn classifiers to a data-only browser format.")
    parser.add_argument("--upper-run", required=True)
    parser.add_argument("--lower-run", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    upper, upper_evaluation, upper_schema = load_run(Path(args.upper_run))
    lower, lower_evaluation, lower_schema = load_run(Path(args.lower_run))
    if upper_schema != lower_schema:
        raise ValueError("upper and lower models use different feature schemas")
    accepted_statuses = {"passed", "completed"}
    if upper_evaluation["status"] not in accepted_statuses or lower_evaluation["status"] not in accepted_statuses:
        raise ValueError("refusing to export a model that did not pass its independent test thresholds")

    artifact = {
        "format": "healthverse-portable-tree-ensemble-v1",
        "version": "multiposture-subject3-chi-v2-20261125",
        "feature_schema": upper_schema,
        "confidence_threshold": 0.65,
        "data_provenance": {
            "dataset": "MultiPosture v1",
            "doi": "10.5281/zenodo.14230872",
            "note": "Real participant landmarks; train/validation/test separated by subject_id.",
        },
        "upper": {"model": upper, "evaluation": upper_evaluation},
        "lower": {"model": lower, "evaluation": lower_evaluation},
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{output} ({output.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
