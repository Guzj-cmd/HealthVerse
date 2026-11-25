"""Distill accepted AI-teacher labels into lightweight structured student models."""

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
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier


def score(y_true, y_pred, labels: list[str]) -> dict:
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
    }


def fit_target(X, y, split, seed: int):
    candidates = {
        "logistic_regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=3000, class_weight="balanced", C=0.5, random_state=seed)),
        "decision_tree": DecisionTreeClassifier(max_depth=5, min_samples_leaf=2, class_weight="balanced", random_state=seed),
        "random_forest": RandomForestClassifier(n_estimators=300, max_depth=8, min_samples_leaf=2, max_features="sqrt", class_weight="balanced_subsample", n_jobs=-1, random_state=seed),
        "hist_gradient_boosting": HistGradientBoostingClassifier(max_iter=250, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=4, l2_regularization=2.0, class_weight="balanced", random_state=seed),
    }
    labels = sorted(y.unique()); history, trained, thresholds = [], {}, {}
    for name, model in candidates.items():
        model.fit(X.iloc[split["train"]], y.iloc[split["train"]])
        threshold = None
        if len(labels) == 2 and hasattr(model, "predict_proba"):
            probability = model.predict_proba(X.iloc[split["validation"]])[:, list(model.classes_).index(labels[1])]
            options = []
            for candidate in [value / 100 for value in range(25, 76, 5)]:
                prediction = [labels[1] if value >= candidate else labels[0] for value in probability]
                options.append((score(y.iloc[split["validation"]], prediction, labels), candidate))
            result, threshold = max(options, key=lambda item: (item[0]["macro_f1"], item[0]["accuracy"], -abs(item[1] - 0.5)))
        else:
            result = score(y.iloc[split["validation"]], model.predict(X.iloc[split["validation"]]), labels)
        history.append({"model": name, "validation": result, "validation_selected_threshold": threshold}); trained[name] = model; thresholds[name] = threshold
    winner = max(history, key=lambda item: (item["validation"]["macro_f1"], item["validation"]["accuracy"]))["model"]
    threshold = thresholds[winner]
    if threshold is not None:
        probability = trained[winner].predict_proba(X.iloc[split["test"]])[:, list(trained[winner].classes_).index(labels[1])]
        prediction = [labels[1] if value >= threshold else labels[0] for value in probability]
    else:
        prediction = trained[winner].predict(X.iloc[split["test"]])
    test = score(y.iloc[split["test"]], prediction, labels)
    return trained[winner], winner, threshold, labels, history, test


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--labels", default="artifacts/teacher/labels.json")
    parser.add_argument("--output", default="artifacts/student")
    parser.add_argument("--config", default="config.json")
    args = parser.parse_args()
    output = Path(args.output); output.mkdir(parents=True, exist_ok=True)
    config = json.loads(Path(args.config).read_text(encoding="utf-8")); seed = int(config["random_seed"])
    teacher = json.loads(Path(args.labels).read_text(encoding="utf-8"))
    if teacher.get("state") != "labeled" or not teacher.get("consensus"):
        raise ValueError("real AI teacher labels are not ready")
    data = pd.read_csv(args.data)
    records = []
    for item in teacher["consensus"]:
        context, label = item["context"], item["teacher_label"]
        # Distill the same observable structured context shown to the teacher.
        # Runtime uses the real-data perception model's pose output plus geometry;
        # unavailable environment fields are intentionally absent.
        record = {
            "observed_upper_posture": context["observed_upper_posture"],
            "observed_lower_posture": context["observed_lower_posture"],
            "trunk_angle_deg": context["derived_trunk_angle_from_vertical_deg"],
            "neck_angle_deg": context["derived_neck_angle_from_vertical_deg"],
            "shoulder_tilt_deg": context["derived_shoulder_tilt_deg"],
            "subject_id": context["subject_id"], "sample_id": context["sample_id"],
            "action": label["recommended_action"], "risk": label["risk_level"],
        }
        records.append(record)
    frame = pd.DataFrame(records); groups = frame["subject_id"]
    outer = GroupShuffleSplit(n_splits=1, test_size=0.23, random_state=seed)
    trainval, test = next(outer.split(frame, frame["action"], groups))
    inner = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=seed)
    train_rel, validation_rel = next(inner.split(frame.iloc[trainval], frame.iloc[trainval]["action"], groups.iloc[trainval]))
    split = {"train": trainval[train_rel], "validation": trainval[validation_rel], "test": test}
    subject_sets = {name: set(groups.iloc[index]) for name, index in split.items()}
    if any(subject_sets[a] & subject_sets[b] for a, b in (("train", "validation"), ("train", "test"), ("validation", "test"))): raise AssertionError("subject leakage")
    for target in ("action", "risk"):
        classes = set(frame[target])
        for name, indices in split.items():
            if set(frame.iloc[indices][target]) != classes: raise ValueError(f"{name} split lacks {target} class; collect more teacher labels")
    structured_columns = ["observed_upper_posture", "observed_lower_posture", "trunk_angle_deg", "neck_angle_deg", "shoulder_tilt_deg"]
    X = pd.get_dummies(frame[structured_columns], columns=["observed_upper_posture", "observed_lower_posture"], dtype=float)
    feature_columns = list(X.columns)
    action_model, action_winner, action_threshold, action_labels, action_history, action_test = fit_target(X, frame["action"], split, seed)
    risk_model, risk_winner, risk_threshold, risk_labels, risk_history, risk_test = fit_target(X, frame["risk"], split, seed)
    coverage = float(teacher["coverage"])
    abstained = sum(any(annotation["label"]["abstain"] for annotation in item["annotations"]) for item in teacher["rejected"])
    teacher_abstention = abstained / int(teacher["attempted"])
    thresholds = config["teacher_distillation"]["student_thresholds"]
    failures = []
    if action_test["accuracy"] < thresholds["accuracy"]: failures.append("action_accuracy")
    if action_test["macro_f1"] < thresholds["macro_f1"]: failures.append("action_macro_f1")
    if coverage < thresholds["minimum_coverage"]: failures.append("teacher_coverage")
    if teacher_abstention > thresholds["maximum_teacher_abstention"]: failures.append("teacher_abstention")
    report = {
        "status": "development_passed" if not failures else "failed",
        "metric_semantics": "agreement with filtered AI-teacher labels, not medical or ergonomic correctness",
        "failed_thresholds": failures,
        "action_student": {"selected_model": action_winner, "validation_selected_threshold": action_threshold, "test": action_test, "labels": action_labels},
        "risk_student": {"selected_model": risk_winner, "validation_selected_threshold": risk_threshold, "test": risk_test, "labels": risk_labels},
        "teacher": {"model": teacher["teacher_model"], "attempted": teacher["attempted"], "accepted": len(teacher["consensus"]), "coverage": coverage, "rejected_for_disagreement_or_confidence": len(teacher["rejected"]), "abstention_rate": teacher_abstention, "prompt_version": teacher["prompt_version"], "prompt_checksum": teacher["prompt_checksum"]},
        "split": {name: {"samples": len(indices), "subjects": sorted(subject_sets[name])} for name, indices in split.items()},
        "student_input": "same observable structured posture context shown to the teacher",
        "environment_action_status": "untrained_missing_observed_environment_fields",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (output / "metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "training_history.json").write_text(json.dumps({"action": action_history, "risk": risk_history}, ensure_ascii=False, indent=2), encoding="utf-8")
    joblib.dump({"action_model": action_model, "risk_model": risk_model, "features": feature_columns, "action_labels": action_labels, "risk_labels": risk_labels, "action_threshold": action_threshold, "risk_threshold": risk_threshold, "report": report}, output / "student_policy.joblib")
    with (output / "splits.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle); writer.writerow(["sample_id", "subject_id", "teacher_action", "teacher_risk", "split"])
        for name, indices in split.items():
            for index in indices: writer.writerow([frame.iloc[index]["sample_id"], frame.iloc[index]["subject_id"], frame.iloc[index]["action"], frame.iloc[index]["risk"], name])
    (output / "model_card.md").write_text(f"""# HealthVerse distilled student model card

- Status: **{report['status']}**
- Training observations: {len(frame)} real MultiPosture participant samples
- Teacher: `{teacher['teacher_model']}`, two-pass exact consensus
- Teacher-label coverage: {coverage:.4f}
- Action student: `{action_winner}`
- Held-out action Accuracy: {action_test['accuracy']:.4f}
- Held-out action Macro-F1: {action_test['macro_f1']:.4f}
- Risk student: `{risk_winner}`
- Held-out risk Accuracy: {risk_test['accuracy']:.4f}
- Held-out risk Macro-F1: {risk_test['macro_f1']:.4f}

All reported predictive metrics measure agreement with filtered AI-teacher labels on participant-held-out real observations. They are not medical accuracy, clinical validity, or proof that the advice improves health. Only `no_action` and `ask_confirm` received supported teacher labels. Environment-dependent actions remain untrained because MultiPosture has no observed monitor/object relation or duration fields.
""", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False)); return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
