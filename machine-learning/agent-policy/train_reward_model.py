"""Train the structured pairwise reward model from real, consented preferences only."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from preference_store import ACTIONS, eligibility, validate_event

NUMERIC = [
    "neck_angle_deg", "shoulder_angle_deg", "duration_min", "monitor_delta_cm", "object_reach_cm",
    "perception_confidence", "relation_confidence", "interrupt_cost",
    "prob_TUP", "prob_TLB", "prob_TLF", "prob_TLR", "prob_TLL",
    "a_rationale_count", "b_rationale_count",
]
CATEGORICAL = ["source_type", "pose_class", "candidate_a_action", "candidate_b_action"]


def load_events(path: Path) -> list[dict]:
    events = []
    if not path.exists():
        return events
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip(): continue
        event = json.loads(line); validate_event(event); events.append(event)
    return events


def event_counts(events: list[dict]) -> dict:
    choices = Counter(event["preference"]["choice"] for event in events)
    actions = Counter(action for event in events for action in (event["candidate_a"]["action"], event["candidate_b"]["action"]))
    return {
        "events": len(events), "decisive_preferences": choices["A"] + choices["B"],
        "participants": len({e["anonymous_participant_id"] for e in events}),
        "sessions": len({e["anonymous_session_id"] for e in events}),
        "choices": dict(choices), "action_exposures": dict(actions),
    }


def row(event: dict, swap: bool = False) -> dict:
    context = event["context"]; a, b = event["candidate_a"], event["candidate_b"]
    choice = event["preference"]["choice"]
    if swap: a, b, choice = b, a, ("B" if choice == "A" else "A")
    values = {
        "source_type": context["source_type"], "pose_class": context["pose_class"],
        "candidate_a_action": a["action"], "candidate_b_action": b["action"],
        "neck_angle_deg": context["neck_angle_deg"], "shoulder_angle_deg": context["shoulder_angle_deg"],
        "duration_min": context["duration_min"], "monitor_delta_cm": context["monitor_delta_cm"],
        "object_reach_cm": context["object_reach_cm"], "perception_confidence": context["perception_confidence"],
        "relation_confidence": context["relation_confidence"], "interrupt_cost": context["interrupt_cost"],
        "a_rationale_count": len(a["rationale_codes"]), "b_rationale_count": len(b["rationale_codes"]),
        "participant": event["anonymous_participant_id"], "session": event["anonymous_session_id"],
        "target": 1 if choice == "A" else 0,
    }
    values.update({f"prob_{name}": value for name, value in context["pose_probs"].items()})
    return values


def expected_calibration_error(y_true: np.ndarray, probability: np.ndarray, bins: int = 10) -> float:
    edges = np.linspace(0, 1, bins + 1); result = 0.0
    for lower, upper in zip(edges[:-1], edges[1:]):
        mask = (probability >= lower) & (probability < upper if upper < 1 else probability <= upper)
        if mask.any(): result += float(mask.mean()) * abs(float(y_true[mask].mean()) - float(probability[mask].mean()))
    return float(result)


def metrics(model, X, y) -> dict:
    probability = model.predict_proba(X)[:, 1]; prediction = (probability >= 0.5).astype(int)
    return {
        "accuracy": float(accuracy_score(y, prediction)),
        "macro_f1": float(f1_score(y, prediction, average="macro", zero_division=0)),
        "roc_auc": float(roc_auc_score(y, probability)),
        "ece": expected_calibration_error(np.asarray(y), probability),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preferences", default="data/preferences.jsonl")
    parser.add_argument("--output", default="artifacts/reward")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--status-only", action="store_true")
    args = parser.parse_args()
    output = Path(args.output); output.mkdir(parents=True, exist_ok=True)
    config = json.loads(Path(args.config).read_text(encoding="utf-8")); policy_config = config["feedback_policy"]
    events = load_events(Path(args.preferences)); counts = event_counts(events); state, blockers = eligibility(counts, policy_config)
    state_report = {"state": state, "counts": counts, "blockers": blockers, "updated_at": datetime.now(timezone.utc).isoformat()}
    (output / "state.json").write_text(json.dumps(state_report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.status_only or state != "eligible":
        print(json.dumps(state_report, ensure_ascii=False)); return 0 if args.status_only else 3

    decisive = [event for event in events if event["preference"]["choice"] in {"A", "B"}]
    frame = pd.DataFrame([row(event) for event in decisive])
    groups = frame["participant"]
    outer = GroupShuffleSplit(n_splits=1, test_size=policy_config["test_participant_fraction"], random_state=config["random_seed"])
    trainval, test = next(outer.split(frame, frame["target"], groups))
    inner = GroupShuffleSplit(n_splits=1, test_size=policy_config["validation_participant_fraction"], random_state=config["random_seed"])
    train_rel, validation_rel = next(inner.split(frame.iloc[trainval], frame.iloc[trainval]["target"], groups.iloc[trainval]))
    train, validation = trainval[train_rel], trainval[validation_rel]
    split = {"train": train, "validation": validation, "test": test}
    for name, indices in split.items():
        if frame.iloc[indices]["target"].nunique() < 2: raise ValueError(f"{name} lacks both A/B outcomes")
    participant_sets = {name: set(frame.iloc[indices]["participant"]) for name, indices in split.items()}
    if any(participant_sets[a] & participant_sets[b] for a, b in (("train", "validation"), ("train", "test"), ("validation", "test"))):
        raise AssertionError("participant leakage")

    # Swap augmentation is applied to training only to reduce left/right presentation bias.
    train_events = [decisive[index] for index in train]
    train_frame = pd.DataFrame([row(event) for event in train_events] + [row(event, swap=True) for event in train_events])
    preprocessor = ColumnTransformer([
        ("numeric", Pipeline([("scale", StandardScaler())]), NUMERIC),
        ("categorical", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL),
    ])
    candidates = {
        "logistic_regression": LogisticRegression(max_iter=3000, class_weight="balanced", random_state=config["random_seed"]),
        "random_forest": RandomForestClassifier(n_estimators=400, min_samples_leaf=4, class_weight="balanced_subsample", n_jobs=-1, random_state=config["random_seed"]),
        "hist_gradient_boosting": HistGradientBoostingClassifier(max_iter=250, learning_rate=0.05, l2_regularization=2.0, random_state=config["random_seed"]),
    }
    feature_columns = NUMERIC + CATEGORICAL
    history, fitted = [], {}
    for name, estimator in candidates.items():
        model = Pipeline([("features", preprocessor), ("model", estimator)])
        model.fit(train_frame[feature_columns], train_frame["target"])
        result = metrics(model, frame.iloc[validation][feature_columns], frame.iloc[validation]["target"])
        history.append({"model": name, "validation": result}); fitted[name] = model
    winner = max(history, key=lambda item: (item["validation"]["macro_f1"], item["validation"]["roc_auc"], -item["validation"]["ece"]))["model"]
    model = fitted[winner]; test_metrics = metrics(model, frame.iloc[test][feature_columns], frame.iloc[test]["target"])
    thresholds = policy_config["thresholds"]
    failures = [name for name in ("accuracy", "macro_f1", "roc_auc") if test_metrics[name] < thresholds[name]]
    if test_metrics["ece"] > thresholds["maximum_ece"]: failures.append("ece")
    final_state = "passed" if not failures else "trained"
    report = {
        "state": final_state, "selected_model": winner, "test": test_metrics, "thresholds": thresholds,
        "failed_thresholds": failures, "counts": counts,
        "split": {name: {"preferences": len(indices), "participants": len(participant_sets[name])} for name, indices in split.items()},
        "group_unit": "anonymous_participant_id", "safety_constraints_in_reward_metrics": False,
        "domain": "HealthVerse office-posture recommendation preferences",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (output / "metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "training_history.json").write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "state.json").write_text(json.dumps({"state": final_state, "counts": counts, "blockers": failures}, ensure_ascii=False, indent=2), encoding="utf-8")
    joblib.dump({"model": model, "features": feature_columns, "action_support": counts["action_exposures"], "report": report}, output / "reward_model.joblib")
    print(json.dumps(report, ensure_ascii=False)); return 0 if final_state == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
