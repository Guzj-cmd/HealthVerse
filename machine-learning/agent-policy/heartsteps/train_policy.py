from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


NUMERIC = [
    "decision_slot",
    "study_day",
    "jbsteps30pre.zero",
    "jbsteps60pre.zero",
    "gfsteps30pre",
    "gfsteps60pre",
    "dec.temperature",
    "dec.windspeed",
    "dec.precipitation.chance",
    "dec.snow",
    "past_suggestions_5",
    "past_suggestions_20",
]
CATEGORICAL = [
    "recognized.activity",
    "dec.location.category",
    "dec.weather.condition",
]
FEATURES = NUMERIC + CATEGORICAL
PROPENSITY = {0: 0.4, 1: 0.6}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _bool(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    return series.astype("string").str.lower().map({"true": True, "false": False})


def load_dataset(path: Path, expected_hash: str) -> pd.DataFrame:
    observed_hash = sha256(path)
    if observed_hash != expected_hash.upper():
        raise RuntimeError(f"suggestions.csv hash mismatch: {observed_hash}")
    raw = pd.read_csv(path, low_memory=False)
    raw["avail_bool"] = _bool(raw["avail"])
    raw["randomized_bool"] = _bool(raw["is.randomized"])
    raw["send_bool"] = _bool(raw["send"])
    raw = raw.sort_values(["user.index", "decision.index"], kind="stable").copy()
    prior_action = raw["send_bool"].fillna(False).infer_objects(copy=False).astype(int)
    raw["past_suggestions_5"] = (
        prior_action.groupby(raw["user.index"], sort=False)
        .transform(lambda values: values.shift(1).rolling(5, min_periods=1).sum())
        .fillna(0.0)
    )
    raw["past_suggestions_20"] = (
        prior_action.groupby(raw["user.index"], sort=False)
        .transform(lambda values: values.shift(1).rolling(20, min_periods=1).sum())
        .fillna(0.0)
    )
    raw["decision_slot"] = pd.to_numeric(raw["sugg.select.slot"], errors="coerce")
    raw["study_day"] = np.floor(pd.to_numeric(raw["decision.index.nogap"], errors="coerce") / 5.0)
    for column in NUMERIC:
        raw[column] = pd.to_numeric(raw[column], errors="coerce")
    planned = pd.to_numeric(raw["decision.index.nogap"], errors="coerce").between(0, 209)
    consistent = raw["randomized_bool"].notna() & raw["send_bool"].notna()
    consistent &= raw["randomized_bool"] == raw["send_bool"]
    selected = raw[raw["avail_bool"].fillna(False) & planned & consistent].copy()
    selected["action"] = selected["send_bool"].astype(int)
    selected["outcome"] = np.log1p(pd.to_numeric(selected["jbsteps30.zero"], errors="coerce"))
    selected = selected[selected["outcome"].notna()].copy()
    selected["participant"] = selected["user.index"].astype(str)
    selected["row_id"] = selected["participant"] + ":" + selected["decision.index"].astype(str)
    if selected["row_id"].duplicated().any():
        raise RuntimeError("duplicate participant/decision rows")
    if selected["participant"].nunique() < 30:
        raise RuntimeError("participant support below frozen protocol")
    return selected.reset_index(drop=True)


def make_preprocessor() -> ColumnTransformer:
    numeric = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median", add_indicator=True)),
            ("scale", StandardScaler()),
        ]
    )
    categorical = Pipeline(
        [
            ("impute", SimpleImputer(strategy="most_frequent")),
            (
                "onehot",
                OneHotEncoder(handle_unknown="ignore", min_frequency=10, sparse_output=False),
            ),
        ]
    )
    return ColumnTransformer(
        [("numeric", numeric, NUMERIC), ("categorical", categorical, CATEGORICAL)],
        remainder="drop",
        sparse_threshold=0.0,
    )


def fit_outcome_models(
    train: pd.DataFrame,
    *,
    seed: int,
    model_kind: str = "extra_trees",
    min_samples_leaf: int = 20,
):
    preprocessor = make_preprocessor()
    transformed = preprocessor.fit_transform(train[FEATURES])
    models: dict[int, object] = {}
    for action in (0, 1):
        mask = train["action"].to_numpy() == action
        if model_kind == "extra_trees":
            model = ExtraTreesRegressor(
                n_estimators=240,
                min_samples_leaf=min_samples_leaf,
                max_features=0.8,
                n_jobs=-1,
                random_state=seed + action,
            )
        elif model_kind == "ridge":
            model = Ridge(alpha=10.0)
        else:
            raise ValueError(f"unsupported model kind: {model_kind}")
        model.fit(transformed[mask], train.loc[mask, "outcome"].to_numpy())
        models[action] = model
    return preprocessor, models


def predict_outcomes(preprocessor, models, frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    transformed = preprocessor.transform(frame[FEATURES])
    return models[0].predict(transformed), models[1].predict(transformed)


def dr_contribution(
    policy: np.ndarray,
    action: np.ndarray,
    outcome: np.ndarray,
    mu0: np.ndarray,
    mu1: np.ndarray,
) -> np.ndarray:
    policy = np.asarray(policy, dtype=np.int64)
    observed_mu = np.where(action == 1, mu1, mu0)
    policy_mu = np.where(policy == 1, mu1, mu0)
    propensity = np.where(action == 1, PROPENSITY[1], PROPENSITY[0])
    return policy_mu + (action == policy) * (outcome - observed_mu) / propensity


def choose_threshold(train: pd.DataFrame, *, seed: int, model_kind: str) -> dict:
    groups = train["participant"].to_numpy()
    action = train["action"].to_numpy(dtype=np.int64)
    outcome = train["outcome"].to_numpy(dtype=np.float64)
    mu0 = np.full(len(train), np.nan)
    mu1 = np.full(len(train), np.nan)
    inner = GroupKFold(n_splits=3)
    for fold, (fit_index, value_index) in enumerate(inner.split(train, action, groups)):
        preprocessor, models = fit_outcome_models(
            train.iloc[fit_index], seed=seed + fold * 10, model_kind=model_kind
        )
        mu0[value_index], mu1[value_index] = predict_outcomes(preprocessor, models, train.iloc[value_index])
    if not np.isfinite(mu0).all() or not np.isfinite(mu1).all():
        raise RuntimeError("incomplete inner cross-fitting")
    benefit = mu1 - mu0
    thresholds = sorted(set([0.0] + [float(np.quantile(benefit, q)) for q in (0.35, 0.45, 0.55, 0.65, 0.75, 0.85)]))
    candidates = []
    no_action = dr_contribution(np.zeros(len(train), dtype=int), action, outcome, mu0, mu1)
    for threshold in thresholds:
        policy = (benefit > threshold).astype(int)
        rate = float(policy.mean())
        value = dr_contribution(policy, action, outcome, mu0, mu1)
        candidates.append(
            {
                "threshold": threshold,
                "suggestion_rate": rate,
                "dr_value": float(value.mean()),
                "uplift_vs_no_action": float((value - no_action).mean()),
            }
        )
    eligible = [row for row in candidates if 0.15 <= row["suggestion_rate"] <= 0.65]
    if not eligible:
        raise RuntimeError("no source-only threshold satisfies the frozen suggestion-rate constraint")
    selected = max(eligible, key=lambda row: (row["uplift_vs_no_action"], row["dr_value"]))
    return {"selected": selected, "candidates": candidates}


def cluster_bootstrap(
    participant: np.ndarray,
    difference: np.ndarray,
    *,
    repeats: int,
    seed: int,
) -> dict:
    unique = np.unique(participant)
    blocks = {name: difference[participant == name] for name in unique}
    rng = np.random.default_rng(seed)
    estimates = np.empty(repeats, dtype=np.float64)
    for index in range(repeats):
        sampled = rng.choice(unique, size=len(unique), replace=True)
        values = np.concatenate([blocks[name] for name in sampled])
        estimates[index] = float(values.mean())
    return {
        "replicates": repeats,
        "estimate": float(difference.mean()),
        "ci_95": [float(np.quantile(estimates, 0.025)), float(np.quantile(estimates, 0.975))],
    }


def effective_sample_size(policy: np.ndarray, action: np.ndarray) -> float:
    propensity = np.where(action == 1, PROPENSITY[1], PROPENSITY[0])
    weight = (policy == action).astype(np.float64) / propensity
    return float(weight.sum() ** 2 / np.square(weight).sum())


def run(data_path: Path, protocol_path: Path, output_dir: Path, model_kind: str) -> dict:
    started = time.time()
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    frame = load_dataset(data_path, protocol["dataset"]["suggestions_sha256"])
    groups = frame["participant"].to_numpy()
    action = frame["action"].to_numpy(dtype=np.int64)
    outcome = frame["outcome"].to_numpy(dtype=np.float64)
    outer = GroupKFold(n_splits=5)
    mu0 = np.full(len(frame), np.nan)
    mu1 = np.full(len(frame), np.nan)
    policy = np.full(len(frame), -1, dtype=np.int64)
    folds = []
    for fold, (train_index, test_index) in enumerate(outer.split(frame, action, groups)):
        train = frame.iloc[train_index]
        test = frame.iloc[test_index]
        selection = choose_threshold(train, seed=20261125 + fold * 100, model_kind=model_kind)
        threshold = float(selection["selected"]["threshold"])
        preprocessor, models = fit_outcome_models(
            train, seed=20261125 + fold * 1000, model_kind=model_kind
        )
        mu0[test_index], mu1[test_index] = predict_outcomes(preprocessor, models, test)
        policy[test_index] = ((mu1[test_index] - mu0[test_index]) > threshold).astype(int)
        train_people = set(train["participant"])
        test_people = set(test["participant"])
        overlap = sorted(train_people & test_people)
        if overlap:
            raise RuntimeError(f"participant leakage: {overlap}")
        folds.append(
            {
                "fold": fold,
                "train_participants": len(train_people),
                "test_participants": len(test_people),
                "test_decision_points": len(test),
                "participant_overlap": 0,
                "source_only_threshold": threshold,
                "source_only_selection": selection,
                "outer_suggestion_rate": float(policy[test_index].mean()),
            }
        )
    if not np.isfinite(mu0).all() or not np.isfinite(mu1).all() or (policy < 0).any():
        raise RuntimeError("incomplete outer cross-fitting")

    learned = dr_contribution(policy, action, outcome, mu0, mu1)
    never = dr_contribution(np.zeros(len(frame), dtype=int), action, outcome, mu0, mu1)
    always = dr_contribution(np.ones(len(frame), dtype=int), action, outcome, mu0, mu1)
    difference = learned - never
    bootstrap = cluster_bootstrap(groups, difference, repeats=2000, seed=20261125)
    ess = effective_sample_size(policy, action)
    suggestion_rate = float(policy.mean())
    action_counts = {str(value): int((action == value).sum()) for value in (0, 1)}
    gate = protocol["quality_gate"]
    failures = []
    if frame["participant"].nunique() < gate["minimum_participants"]:
        failures.append("participants")
    if len(frame) < gate["minimum_decision_points"]:
        failures.append("decision_points")
    if min(action_counts.values()) < gate["minimum_action_support_each"]:
        failures.append("action_support")
    if ess < gate["minimum_matched_policy_ess"]:
        failures.append("matched_policy_ess")
    if not gate["minimum_suggestion_rate"] <= suggestion_rate <= gate["maximum_suggestion_rate"]:
        failures.append("suggestion_rate")
    if float(difference.mean()) <= gate["minimum_uplift_vs_never_suggest_log_steps"]:
        failures.append("uplift_vs_never_suggest")
    if bootstrap["ci_95"][0] <= gate["minimum_cluster_bootstrap_95_ci_lower"]:
        failures.append("cluster_bootstrap_ci_lower")
    if any(fold["participant_overlap"] != gate["required_subject_overlap"] for fold in folds):
        failures.append("participant_overlap")

    result = {
        "status": "PASSED" if not failures else "REJECTED",
        "dataset": {
            "name": protocol["dataset"]["name"],
            "commit": protocol["dataset"]["commit"],
            "suggestions_sha256": sha256(data_path),
            "license": protocol["dataset"]["license"],
            "participants": int(frame["participant"].nunique()),
            "decision_points": len(frame),
            "action_counts": action_counts,
            "outcome": protocol["outcome"],
        },
        "protocol": {
            "outer": protocol["evaluation"]["outer"],
            "inner": protocol["evaluation"]["inner"],
            "estimator": protocol["evaluation"]["estimator"],
            "features": FEATURES,
            "forbidden_features": protocol["forbidden_features"],
            "propensity": {"no_suggestion": 0.4, "suggestion": 0.6},
            "outcome_model": model_kind,
        },
        "folds": folds,
        "frozen_evaluation": {
            "learned_policy_dr_value_log_steps": float(learned.mean()),
            "never_suggest_dr_value_log_steps": float(never.mean()),
            "always_suggest_dr_value_log_steps": float(always.mean()),
            "uplift_vs_never_suggest_log_steps": float(difference.mean()),
            "suggestion_rate": suggestion_rate,
            "matched_policy_effective_sample_size": ess,
            "participant_cluster_bootstrap": bootstrap,
        },
        "quality_gate": {"thresholds": gate, "failures": failures},
        "runtime_seconds": time.time() - started,
        "claim_scope": "contextual activity-suggestion policy only; not diagnosis, treatment, or ergonomic adjustment",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "metrics.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (output_dir / "fold_predictions.csv").write_text(
        pd.DataFrame(
            {
                "row_id": frame["row_id"],
                "participant": frame["participant"],
                "observed_action": action,
                "outcome_log_steps": outcome,
                "mu0": mu0,
                "mu1": mu1,
                "policy_action": policy,
                "dr_value": learned,
                "dr_uplift_vs_never": difference,
            }
        ).to_csv(index=False),
        encoding="utf-8",
    )
    if result["status"] == "PASSED":
        final_selection = choose_threshold(frame, seed=20261999, model_kind=model_kind)
        final_preprocessor, final_models = fit_outcome_models(
            frame, seed=20261999, model_kind=model_kind
        )
        joblib.dump(
            {
                "preprocessor": final_preprocessor,
                "models": final_models,
                "threshold": final_selection["selected"]["threshold"],
                "features": FEATURES,
                "actions": {0: "no_action", 1: "offer_activity_suggestion"},
                "scope": "activity_suggestion_only",
            },
            output_dir / "policy.joblib",
        )
        (output_dir / "final_source_only_selection.json").write_text(
            json.dumps(final_selection, indent=2) + "\n", encoding="utf-8"
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, default=Path(__file__).with_name("protocol.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", choices=["extra_trees", "ridge"], default="extra_trees")
    args = parser.parse_args()
    result = run(
        args.data.resolve(), args.protocol.resolve(), args.output.resolve(), args.model
    )
    print(json.dumps({"status": result["status"], "evaluation": result["frozen_evaluation"], "failures": result["quality_gate"]["failures"]}, indent=2))


if __name__ == "__main__":
    main()

