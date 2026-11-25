"""Train a real-data sitting-posture perception model on MultiPosture."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, recall_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

LABELS = ["TLB", "TLF", "TLL", "TLR", "TUP"]


def calculate_metrics(y_true, y_pred) -> dict:
    recall = recall_score(y_true, y_pred, labels=LABELS, average=None, zero_division=0)
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, labels=LABELS, average="macro", zero_division=0)),
        "per_class_recall": {label: float(value) for label, value in zip(LABELS, recall)},
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=LABELS).tolist(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--output", default="artifacts/perception")
    parser.add_argument("--config", default="config.json")
    args = parser.parse_args()
    output = Path(args.output); output.mkdir(parents=True, exist_ok=True)
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    settings = config["perception"]; seed = int(config["random_seed"])
    data = pd.read_csv(args.data)
    required = {"subject", "upperbody_label", "lowerbody_label"}
    if not required.issubset(data.columns):
        raise ValueError(f"MultiPosture columns missing: {sorted(required - set(data.columns))}")
    features = [column for column in data.columns if column not in required]
    if len(features) != 99 or data[features].isna().any().any():
        raise ValueError("expected 99 complete MediaPipe coordinate features")
    X, y, groups = data[features], data["upperbody_label"], data["subject"].astype(str)

    outer = GroupShuffleSplit(n_splits=1, test_size=settings["test_subject_fraction"], random_state=seed)
    trainval_idx, test_idx = next(outer.split(X, y, groups))
    inner = GroupShuffleSplit(n_splits=1, test_size=settings["validation_subject_fraction"], random_state=seed)
    train_rel, validation_rel = next(inner.split(X.iloc[trainval_idx], y.iloc[trainval_idx], groups.iloc[trainval_idx]))
    train_idx, validation_idx = trainval_idx[train_rel], trainval_idx[validation_rel]
    split = {"train": train_idx, "validation": validation_idx, "test": test_idx}
    subject_sets = {name: set(groups.iloc[index]) for name, index in split.items()}
    if any(subject_sets[a] & subject_sets[b] for a, b in (("train", "validation"), ("train", "test"), ("validation", "test"))):
        raise AssertionError("subject leakage detected")
    for name, index in split.items():
        missing = set(LABELS) - set(y.iloc[index])
        if missing:
            raise ValueError(f"{name} split lacks classes: {sorted(missing)}")

    candidates = {
        "logistic_regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=3000, C=1.0, class_weight="balanced", random_state=seed)),
        "random_forest": RandomForestClassifier(n_estimators=400, max_features="sqrt", min_samples_leaf=1, class_weight="balanced_subsample", n_jobs=-1, random_state=seed),
        "hist_gradient_boosting": HistGradientBoostingClassifier(max_iter=300, learning_rate=0.07, max_leaf_nodes=31, l2_regularization=1.0, random_state=seed),
    }
    history, trained = [], {}
    for name, model in candidates.items():
        model.fit(X.iloc[train_idx], y.iloc[train_idx])
        result = calculate_metrics(y.iloc[validation_idx], model.predict(X.iloc[validation_idx]))
        history.append({"model": name, "validation": result})
        trained[name] = model
    winner = max(history, key=lambda row: (row["validation"]["macro_f1"], row["validation"]["accuracy"]))["model"]
    model = trained[winner]
    test_metrics = calculate_metrics(y.iloc[test_idx], model.predict(X.iloc[test_idx]))
    thresholds = settings["thresholds"]
    failures = []
    if test_metrics["accuracy"] < thresholds["accuracy"]: failures.append("accuracy")
    if test_metrics["macro_f1"] < thresholds["macro_f1"]: failures.append("macro_f1")
    for label, value in test_metrics["per_class_recall"].items():
        if value < thresholds["minimum_class_recall"]: failures.append(f"recall:{label}")
    report = {
        "benchmark_type": "perception",
        "status": "passed" if not failures else "failed",
        "failed_thresholds": failures,
        "selected_model": winner,
        "test": test_metrics,
        "thresholds": thresholds,
        "dataset": {"name": "MultiPosture v1", "doi": "10.5281/zenodo.14230872", "rows_loaded": len(data), "participants": int(groups.nunique()), "coordinate_features": len(features)},
        "split": {name: {"rows": len(index), "subjects": sorted(subject_sets[name])} for name, index in split.items()},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "scope": "upper-body sitting posture perception; not relation or recommendation policy",
    }
    (output / "metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "training_history.json").write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    joblib.dump({"model": model, "features": features, "labels": LABELS, "report": report}, output / "perception_model.joblib")
    with (output / "confusion_matrix.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle); writer.writerow(["actual\\predicted", *LABELS])
        for label, row in zip(LABELS, test_metrics["confusion_matrix"]): writer.writerow([label, *row])
    with (output / "splits.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle); writer.writerow(["row_index", "subject", "upperbody_label", "split"])
        for name, indices in split.items():
            for index in indices: writer.writerow([int(index), groups.iloc[index], y.iloc[index], name])
    recalls = "\n".join(f"- `{label}`: {value:.4f}" for label, value in test_metrics["per_class_recall"].items())
    (output / "model_card.md").write_text(f"""# MultiPosture perception model card

- Data: real, expert-validated MultiPosture v1 skeletal frames (Zenodo 14230872)
- Selected on validation: `{winner}`
- Independent participant-held-out test accuracy: `{test_metrics['accuracy']:.4f}`
- Independent participant-held-out test Macro-F1: `{test_metrics['macro_f1']:.4f}`
- Gate: **{report['status']}**

## Test recall

{recalls}

## Scope

This model recognizes five upper-body sitting-posture labels. It does not recognize monitor/object relations and does not choose recommendations. The 4,794-row downloaded CSV contains 99 numeric MediaPipe coordinates even though the Zenodo prose summarizes an 11-joint subset; this run records the inspected file shape rather than silently assuming the prose shape.

## Limitations

Only 13 participants are present. Subject-disjoint evaluation reduces frame leakage but does not establish demographic, camera, home/office, or clinical generalization. It is not a medical diagnostic model.
""", encoding="utf-8")
    print(json.dumps({"status": report["status"], "selected_model": winner, "test": test_metrics}, ensure_ascii=False))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
