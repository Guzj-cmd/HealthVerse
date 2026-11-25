from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.base import clone
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, recall_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from hvml.features import schema
from hvml.io import load_samples
from hvml.modeling import grouped_split, load_config, matrix


def evaluate(y_true: np.ndarray, y_pred: np.ndarray, labels: list[str]) -> dict[str, object]:
    recalls = recall_score(y_true, y_pred, labels=labels, average=None, zero_division=0)
    return {
        "sample_count": int(len(y_true)),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
        "per_class_recall": {label: float(value) for label, value in zip(labels, recalls)},
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
    }


def candidates(seed: int) -> dict[str, object]:
    # The feature vector follows EduSense's body-scale normalization and
    # keypoint-pair direction/distance representation, augmented by joint angles.
    # Only the development subjects are used to select among these fixed candidates.
    return {
        "random_forest_half_features": RandomForestClassifier(
            n_estimators=200, max_depth=None, min_samples_leaf=1,
            max_features=0.5, class_weight="balanced_subsample",
            random_state=seed, n_jobs=-1,
        ),
        "extra_trees_half_features": ExtraTreesClassifier(
            n_estimators=250, max_depth=None, min_samples_leaf=1,
            max_features=0.5, class_weight="balanced",
            random_state=seed, n_jobs=-1,
        ),
        "hist_gradient_boosting_31": HistGradientBoostingClassifier(
            max_iter=200, learning_rate=0.05, max_leaf_nodes=31,
            l2_regularization=0.1, class_weight="balanced", random_state=seed,
        ),
        "rbf_svc_c10": make_pipeline(
            StandardScaler(),
            SVC(C=10.0, gamma="scale", class_weight="balanced", probability=False, random_state=seed),
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Leakage-resistant CHI/IMWUT-inspired posture training")
    parser.add_argument("--data", required=True)
    parser.add_argument("--config", default="config-subject3.json")
    parser.add_argument("--output", required=True)
    parser.add_argument("--cv-folds", type=int, default=3)
    args = parser.parse_args()

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    config = load_config(args.config)
    samples = load_samples(args.data)
    labels = sorted({sample.label for sample in samples})
    split = grouped_split(samples, config)
    development_indices = np.concatenate([split["train"], split["validation"]])
    test_indices = split["test"]
    X_dev, y_dev = matrix([samples[i] for i in development_indices])
    X_test, y_test = matrix([samples[i] for i in test_indices])
    groups_dev = np.asarray([samples[i].subject_id for i in development_indices])
    cv = GroupKFold(n_splits=args.cv_folds)

    candidate_rows: list[dict[str, object]] = []
    candidate_fold_rows: list[dict[str, object]] = []
    model_candidates = candidates(int(config["random_seed"]))
    for name, prototype in model_candidates.items():
        oof = np.empty(len(y_dev), dtype=y_dev.dtype)
        for fold, (train_idx, validation_idx) in enumerate(cv.split(X_dev, y_dev, groups_dev), start=1):
            model = clone(prototype)
            model.fit(X_dev[train_idx], y_dev[train_idx])
            prediction = model.predict(X_dev[validation_idx])
            oof[validation_idx] = prediction
            fold_result = evaluate(y_dev[validation_idx], prediction, labels)
            candidate_fold_rows.append({
                "candidate": name,
                "fold": fold,
                "validation_subjects": sorted(set(groups_dev[validation_idx].tolist())),
                "accuracy": fold_result["accuracy"],
                "macro_f1": fold_result["macro_f1"],
            })
        pooled = evaluate(y_dev, oof, labels)
        candidate_rows.append({"candidate": name, "development_group_cv": pooled})
        (output / "candidate_history.json").write_text(json.dumps(candidate_rows, ensure_ascii=False, indent=2), encoding="utf-8")
        (output / "fold_history.json").write_text(json.dumps(candidate_fold_rows, ensure_ascii=False, indent=2), encoding="utf-8")

    winner_row = max(
        candidate_rows,
        key=lambda row: (
            row["development_group_cv"]["macro_f1"],
            row["development_group_cv"]["accuracy"],
        ),
    )
    winner_name = str(winner_row["candidate"])
    winner = clone(model_candidates[winner_name])
    winner.fit(X_dev, y_dev)
    # This is the only test-set prediction in the selection procedure.
    test_prediction = winner.predict(X_test)
    test_result = evaluate(y_test, test_prediction, labels)

    report = {
        "experiment_status": "completed",
        "target_accuracy": 1.0,
        "target_reached": bool(test_result["accuracy"] == 1.0 and test_result["macro_f1"] == 1.0),
        "selection_rule": "highest pooled GroupKFold Macro-F1 on development subjects; test evaluated once after selection",
        "selected_model": winner_name,
        "development_group_cv": winner_row["development_group_cv"],
        "test": test_result,
        "split": {
            "development_subjects": sorted(set(groups_dev.tolist())),
            "test_subjects": sorted({samples[i].subject_id for i in test_indices}),
            "development_samples": int(len(y_dev)),
            "test_samples": int(len(y_test)),
        },
        "feature_method": "EduSense-style scale-normalized keypoint-pair direction/distance features plus normalized landmarks, visibility and joint-angle features",
        "dataset": Path(args.data).name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "limitations": [
            "The public landmark table cannot measure camera-to-pose-detector coverage.",
            "This dataset has 13 participants; 100% on a frozen split would not prove universal generalization.",
            "The same historical split was used by earlier project runs, so results are development evidence rather than a final external benchmark.",
        ],
    }
    (output / "metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "candidate_history.json").write_text(json.dumps(candidate_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "fold_history.json").write_text(json.dumps(candidate_fold_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    joblib.dump({
        "model": winner,
        "labels": labels,
        "feature_schema": schema(),
        "config": config,
        "metadata": {
            "selected_model": winner_name,
            "method": "chi-imwut-inspired-v1",
            "test_subject_ids": report["split"]["test_subjects"],
        },
    }, output / "model.joblib")

    with (output / "splits.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["sample_id", "subject_id", "label", "split"])
        for name, indices in (("development", development_indices), ("test", test_indices)):
            for i in indices:
                sample = samples[i]
                writer.writerow([sample.sample_id, sample.subject_id, sample.label, name])

    with (output / "confusion_matrix.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["actual\\predicted", *labels])
        for label, row in zip(labels, test_result["confusion_matrix"]):
            writer.writerow([label, *row])

    target_note = "达到预设 100% 目标" if report["target_reached"] else "未达到 100%，保留真实误差并停止在无泄漏的最佳候选"
    (output / "model_card.md").write_text(
        f"# CHI/IMWUT-Inspired Posture Model\n\n"
        f"- Result: **{target_note}**\n"
        f"- Selected model: `{winner_name}`\n"
        f"- Development GroupKFold Accuracy / Macro-F1: `{winner_row['development_group_cv']['accuracy']:.4f}` / `{winner_row['development_group_cv']['macro_f1']:.4f}`\n"
        f"- Frozen subject-disjoint test Accuracy / Macro-F1: `{test_result['accuracy']:.4f}` / `{test_result['macro_f1']:.4f}`\n"
        f"- Test subjects: `{', '.join(report['split']['test_subjects'])}`\n\n"
        "## Method\n\n"
        "The representation follows EduSense: body-scale normalization and pairwise keypoint direction/distance features. HealthVerse also includes normalized MediaPipe coordinates, visibility, and interpretable joint/lean angles. Candidate selection uses GroupKFold over development subjects. The frozen test subjects are evaluated only after a winner is selected.\n\n"
        "## Claim boundary\n\n"
        "This is real training on MultiPosture landmarks, not simulated metrics. It is conditional on a pose being detected and is not a medical diagnostic model. The 13-participant dataset is too small to establish universal performance; an untouched external participant cohort remains necessary.\n",
        encoding="utf-8",
    )
    print(json.dumps({"selected_model": winner_name, "target_reached": report["target_reached"], "test": test_result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
