"""Nested participant-disjoint BEHAVE relation training with causal temporal features."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, recall_score
from sklearn.model_selection import GroupKFold


SUBJECT_PATTERN = re.compile(r"_Sub(\d+)_")


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def classify_sequence(name: str, classes: dict[str, list[str]], excluded: set[str]) -> str | None:
    suffix = name.split("_", 2)[-1]
    if suffix in excluded:
        return None
    matches = [label for label, suffixes in classes.items() if suffix in suffixes]
    if len(matches) > 1:
        raise ValueError(f"sequence {name!r} matches multiple classes: {matches}")
    return matches[0] if matches else None


def common_frame_indices(human_times: np.ndarray, object_times: np.ndarray) -> tuple[np.ndarray, np.ndarray, list[str]]:
    human_index = {str(value): index for index, value in enumerate(human_times.tolist())}
    object_index = {str(value): index for index, value in enumerate(object_times.tolist())}
    common = sorted(
        set(human_index) & set(object_index),
        key=lambda value: float(value.removeprefix("t")),
    )
    if not common:
        raise ValueError("human and object fits have no common timestamps")
    return (
        np.asarray([human_index[value] for value in common], dtype=int),
        np.asarray([object_index[value] for value in common], dtype=int),
        common,
    )


def sample_indices(count: int, maximum: int, trim_fraction: float) -> np.ndarray:
    lower = int(np.floor(count * trim_fraction))
    upper = int(np.ceil(count * (1.0 - trim_fraction))) - 1
    if upper <= lower:
        lower, upper = 0, count - 1
    return np.unique(np.linspace(lower, upper, min(maximum, upper - lower + 1), dtype=int))


def causal_mean_std(values: np.ndarray, window: int) -> tuple[np.ndarray, np.ndarray]:
    """Return past-only rolling mean/std, including the current frame."""
    values64 = np.asarray(values, dtype=np.float64)
    prefix = np.vstack([np.zeros((1, values64.shape[1])), np.cumsum(values64, axis=0)])
    prefix_sq = np.vstack([np.zeros((1, values64.shape[1])), np.cumsum(values64 * values64, axis=0)])
    means = np.empty_like(values64)
    stds = np.empty_like(values64)
    for end in range(len(values64)):
        start = max(0, end - window + 1)
        count = end - start + 1
        total = prefix[end + 1] - prefix[start]
        total_sq = prefix_sq[end + 1] - prefix_sq[start]
        mean = total / count
        variance = np.maximum(total_sq / count - mean * mean, 0.0)
        means[end] = mean
        stds[end] = np.sqrt(variance)
    return means.astype(np.float32), stds.astype(np.float32)


def sequence_features(path: Path, config: dict) -> tuple[np.ndarray, np.ndarray, list[str]]:
    with np.load(path / "smpl_fit_all.npz") as human, np.load(path / "object_fit_all.npz") as obj:
        human_idx, object_idx, times = common_frame_indices(human["frame_times"], obj["frame_times"])
        pose = np.asarray(human["poses"][human_idx], dtype=np.float32)
        human_trans = np.asarray(human["trans"][human_idx], dtype=np.float32)
        object_angles = np.asarray(obj["angles"][object_idx], dtype=np.float32)
        object_trans = np.asarray(obj["trans"][object_idx], dtype=np.float32)
    relative = object_trans - human_trans
    pose_delta = np.vstack([np.zeros((1, 156), dtype=np.float32), np.diff(pose, axis=0)])
    human_delta = np.vstack([np.zeros((1, 3), dtype=np.float32), np.diff(human_trans, axis=0)])
    object_delta = np.vstack([np.zeros((1, 3), dtype=np.float32), np.diff(object_trans, axis=0)])
    relative_delta = np.vstack([np.zeros((1, 3), dtype=np.float32), np.diff(relative, axis=0)])
    object_angular_delta = np.vstack([np.zeros((1, 3), dtype=np.float32), np.diff(object_angles, axis=0)])
    baseline = np.hstack([
        pose, human_trans, relative, object_angles,
        pose_delta, human_delta, object_delta, relative_delta,
    ]).astype(np.float32, copy=False)

    joint_angular_speed = np.linalg.norm(pose_delta.reshape(-1, 52, 3), axis=2) * 30.0
    relative_velocity = relative_delta * 30.0
    object_angular_velocity = object_angular_delta * 30.0
    motion_compact = np.hstack([joint_angular_speed, relative_velocity, object_angular_velocity])
    rolling_mean, rolling_std = causal_mean_std(motion_compact, int(config["causal_window_frames"]))
    scalar_speeds = np.column_stack([
        np.linalg.norm(human_delta, axis=1),
        np.linalg.norm(object_delta, axis=1),
        np.linalg.norm(relative_delta, axis=1),
        np.linalg.norm(object_angular_delta, axis=1),
    ]) * 30.0
    scalar_mean, scalar_std = causal_mean_std(scalar_speeds, int(config["causal_window_frames"]))
    temporal = np.hstack([
        baseline,
        object_angular_velocity,
        rolling_mean,
        rolling_std,
        scalar_mean,
        scalar_std,
    ]).astype(np.float32, copy=False)
    if not np.isfinite(temporal).all():
        raise ValueError(f"non-finite temporal feature in {path.name}")
    selected = sample_indices(
        len(baseline), int(config["samples_per_sequence"]), float(config["temporal_trim_fraction"])
    )
    return baseline[selected], temporal[selected], [times[index] for index in selected]


def load_dataset(config: dict, repo_root: Path) -> dict:
    root = repo_root / config["local_params"]
    records = []
    for path in sorted(item for item in root.iterdir() if item.is_dir()):
        label = classify_sequence(path.name, config["classes"], set(config["excluded_ambiguous_suffixes"]))
        if label is None:
            continue
        match = SUBJECT_PATTERN.search(path.name)
        if not match:
            raise ValueError(f"cannot parse subject from {path.name}")
        baseline, temporal, times = sequence_features(path, config)
        records.append((path.name, f"Sub{match.group(1)}", label, baseline, temporal, times))
    return {
        "baseline": np.vstack([record[3] for record in records]),
        "temporal": np.vstack([record[4] for record in records]),
        "labels": np.concatenate([np.repeat(record[2], len(record[3])) for record in records]),
        "subjects": np.concatenate([np.repeat(record[1], len(record[3])) for record in records]),
        "sequences": np.concatenate([np.repeat(record[0], len(record[3])) for record in records]),
        "times": [time for record in records for time in record[5]],
    }


def build_estimator(candidate: dict, seed: int):
    common = dict(
        random_state=seed,
        class_weight=candidate["class_weight"],
    )
    if candidate["estimator"] == "extra_trees":
        return ExtraTreesClassifier(
            n_estimators=int(candidate["n_estimators"]),
            min_samples_leaf=int(candidate["min_samples_leaf"]),
            max_features=candidate["max_features"],
            n_jobs=-1,
            **common,
        )
    if candidate["estimator"] == "random_forest":
        return RandomForestClassifier(
            n_estimators=int(candidate["n_estimators"]),
            min_samples_leaf=int(candidate["min_samples_leaf"]),
            max_features=candidate["max_features"],
            n_jobs=-1,
            **common,
        )
    if candidate["estimator"] == "hist_gradient_boosting":
        return HistGradientBoostingClassifier(
            max_iter=int(candidate["max_iter"]),
            learning_rate=float(candidate["learning_rate"]),
            max_leaf_nodes=int(candidate["max_leaf_nodes"]),
            min_samples_leaf=int(candidate["min_samples_leaf"]),
            l2_regularization=float(candidate["l2_regularization"]),
            **common,
        )
    raise ValueError(f"unknown estimator: {candidate['estimator']}")


def metrics(y_true: np.ndarray, y_pred: np.ndarray, labels: list[str]) -> dict:
    recalls = recall_score(y_true, y_pred, labels=labels, average=None, zero_division=0)
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
        "per_class_recall": {label: float(value) for label, value in zip(labels, recalls)},
        "minimum_class_recall": float(np.min(recalls)),
        "class_support": {label: int(np.sum(y_true == label)) for label in labels},
    }


def inner_score(candidate: dict, data: dict, development: np.ndarray, config: dict, seed_offset: int) -> dict:
    labels = list(config["classes"])
    x = data[candidate["feature_set"]]
    y = data["labels"]
    groups = data["subjects"]
    splitter = GroupKFold(n_splits=int(config["inner_group_folds"]))
    truth: list[str] = []
    predicted: list[str] = []
    inner_folds = []
    for inner_index, (train_local, valid_local) in enumerate(
        splitter.split(x[development], y[development], groups[development])
    ):
        train_idx = development[train_local]
        valid_idx = development[valid_local]
        model = build_estimator(candidate, int(config["random_seed"]) + seed_offset * 100 + inner_index)
        model.fit(x[train_idx], y[train_idx])
        fold_pred = model.predict(x[valid_idx])
        truth.extend(y[valid_idx].tolist())
        predicted.extend(fold_pred.tolist())
        fold_metric = metrics(y[valid_idx], fold_pred, labels)
        fold_metric.update({
            "validation_subjects": sorted(np.unique(groups[valid_idx]).tolist()),
            "train_subjects": sorted(np.unique(groups[train_idx]).tolist()),
        })
        inner_folds.append(fold_metric)
    aggregate = metrics(np.asarray(truth), np.asarray(predicted), labels)
    return {"candidate": candidate["name"], "aggregate": aggregate, "folds": inner_folds}


def selection_key(result: dict, candidate: dict) -> tuple[float, float, float, int]:
    score = result["aggregate"]
    return (
        score["macro_f1"],
        score["minimum_class_recall"],
        score["accuracy"],
        -int(candidate["complexity_rank"]),
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("machine-learning/datasets/behave-relation-v2.json"))
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    config_path = args.config if args.config.is_absolute() else repo_root / args.config
    config = load_json(config_path)
    output = repo_root / config["output_dir"]
    output.mkdir(parents=True, exist_ok=True)
    data = load_dataset(config, repo_root)
    labels = list(config["classes"])
    subjects = data["subjects"]
    unique_subjects = sorted(np.unique(subjects).tolist())
    candidates = config["candidates"]
    by_name = {candidate["name"]: candidate for candidate in candidates}

    outer_history = []
    candidate_history = []
    split_rows = []
    all_true: list[str] = []
    all_pred: list[str] = []
    for outer_index, holdout in enumerate(unique_subjects):
        test = np.flatnonzero(subjects == holdout)
        development = np.flatnonzero(subjects != holdout)
        results = [inner_score(candidate, data, development, config, outer_index) for candidate in candidates]
        selected_result = max(results, key=lambda result: selection_key(result, by_name[result["candidate"]]))
        selected = by_name[selected_result["candidate"]]
        x = data[selected["feature_set"]]
        model = build_estimator(selected, int(config["random_seed"]) + 1000 + outer_index)
        model.fit(x[development], data["labels"][development])
        prediction = model.predict(x[test])
        outer_metric = metrics(data["labels"][test], prediction, labels)
        outer_metric.update({
            "holdout_subject": holdout,
            "selected_candidate": selected["name"],
            "selected_feature_set": selected["feature_set"],
            "inner_selected_metrics": selected_result["aggregate"],
            "train_samples": int(len(development)),
            "test_samples": int(len(test)),
        })
        outer_history.append(outer_metric)
        candidate_history.append({
            "holdout_subject": holdout,
            "selection_rule": config["selection_rule"],
            "selected_candidate": selected["name"],
            "candidates": results,
        })
        all_true.extend(data["labels"][test].tolist())
        all_pred.extend(prediction.tolist())
        for local_index, sample_index in enumerate(test):
            split_rows.append({
                "sequence": data["sequences"][sample_index],
                "subject": subjects[sample_index],
                "frame_time": data["times"][sample_index],
                "true_label": data["labels"][sample_index],
                "predicted_label": prediction[local_index],
                "fold": holdout,
                "selected_candidate": selected["name"],
            })

    aggregate = metrics(np.asarray(all_true), np.asarray(all_pred), labels)
    matrix = confusion_matrix(all_true, all_pred, labels=labels)
    gate = config["quality_gate"]
    gate_failures = []
    if aggregate["macro_f1"] < float(gate["minimum_aggregate_macro_f1"]):
        gate_failures.append("aggregate macro-F1 below threshold")
    if aggregate["minimum_class_recall"] < float(gate["minimum_aggregate_class_recall"]):
        gate_failures.append("minimum aggregate class recall below threshold")

    v1 = load_json(repo_root / config["v1_metrics"])["aggregate_loso"]
    v1_min_recall = min(v1["per_class_recall"].values())
    improves_macro = aggregate["macro_f1"] > float(v1["macro_f1"])
    improves_min_recall = aggregate["minimum_class_recall"] > v1_min_recall
    replacement = "v2" if improves_macro and improves_min_recall else "v1"

    all_indices = np.arange(len(data["labels"]), dtype=int)
    final_scores = [inner_score(candidate, data, all_indices, config, 99) for candidate in candidates]
    final_selected_result = max(final_scores, key=lambda result: selection_key(result, by_name[result["candidate"]]))
    final_candidate = by_name[final_selected_result["candidate"]]
    final_model = build_estimator(final_candidate, int(config["random_seed"]) + 9999)
    final_model.fit(data[final_candidate["feature_set"]], data["labels"])
    model_path = output / "model.joblib"
    joblib.dump({
        "model": final_model,
        "candidate": final_candidate,
        "labels": labels,
        "feature_dimensions": int(data[final_candidate["feature_set"]].shape[1]),
        "dataset_license": config["license"],
        "redistribution_notice": "Keep local unless BEHAVE permits derived-weight redistribution.",
    }, model_path)

    sequence_labels = {
        sequence: data["labels"][np.flatnonzero(data["sequences"] == sequence)[0]]
        for sequence in np.unique(data["sequences"])
    }
    summary = {
        "dataset": {
            "id": config["dataset_id"],
            "source_url": config["source_url"],
            "license": config["license"],
            "raw_data_redistributed": False,
        },
        "protocol": {
            "outer": "leave-one-subject-out; outer test evaluated once per subject",
            "inner": f"{config['inner_group_folds']}-fold GroupKFold on development subjects only",
            "selection_rule": config["selection_rule"],
            "replacement_rule": config["replacement_rule"],
            "causal_window_frames": int(config["causal_window_frames"]),
        },
        "data_summary": {
            "subjects": unique_subjects,
            "subject_count": len(unique_subjects),
            "sequence_count": int(np.unique(data["sequences"]).size),
            "sample_count": int(len(data["labels"])),
            "samples_per_class": dict(Counter(data["labels"].tolist())),
            "sequences_per_class": dict(Counter(sequence_labels.values())),
            "baseline_dimensions": int(data["baseline"].shape[1]),
            "temporal_dimensions": int(data["temporal"].shape[1]),
        },
        "aggregate_nested_loso": aggregate,
        "quality_gate": {
            "thresholds": gate,
            "status": "passed" if not gate_failures else "failed",
            "failures": gate_failures,
        },
        "comparison_to_v1": {
            "v1_macro_f1": float(v1["macro_f1"]),
            "v2_macro_f1": aggregate["macro_f1"],
            "macro_f1_delta": aggregate["macro_f1"] - float(v1["macro_f1"]),
            "v1_minimum_class_recall": v1_min_recall,
            "v2_minimum_class_recall": aggregate["minimum_class_recall"],
            "minimum_class_recall_delta": aggregate["minimum_class_recall"] - v1_min_recall,
            "improves_both_required_metrics": improves_macro and improves_min_recall,
            "deployment_candidate": replacement,
        },
        "outer_candidate_selection_counts": dict(Counter(
            fold["selected_candidate"] for fold in outer_history
        )),
        "final_full_data_candidate": {
            "name": final_candidate["name"],
            "feature_set": final_candidate["feature_set"],
            "inner_oof_metrics": final_selected_result["aggregate"],
        },
        "local_model_artifact": {
            "path": "model.joblib",
            "sha256": sha256(model_path),
            "tracked_by_git": False,
        },
        "limitations": [
            "Interaction labels come from BEHAVE sequence names, not ergonomic or medical outcome annotations.",
            "Temporal statistics are causal past-only windows, but input still requires fitted SMPL and object transforms.",
            "Sub08 has no table_lean test support; aggregate outer predictions contain all classes.",
            "Nested selection prevents direct outer-test tuning, but seven participants still yield wide uncertainty.",
        ],
    }
    (output / "metrics.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (output / "outer_fold_history.json").write_text(json.dumps(outer_history, indent=2), encoding="utf-8")
    (output / "candidate_history.json").write_text(json.dumps(candidate_history, indent=2), encoding="utf-8")
    (output / "final_candidate_history.json").write_text(json.dumps(final_scores, indent=2), encoding="utf-8")
    with (output / "confusion_matrix.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["true\\pred", *labels])
        for label, row in zip(labels, matrix):
            writer.writerow([label, *row.tolist()])
    with (output / "splits.csv").open("w", newline="", encoding="utf-8") as handle:
        fieldnames = ["sequence", "subject", "frame_time", "true_label", "predicted_label", "fold", "selected_candidate"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(split_rows)
    with (output / "ablation_summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["outer_holdout", "candidate", "feature_set", "inner_macro_f1", "inner_min_recall", "inner_accuracy", "selected"])
        for outer in candidate_history:
            for result in outer["candidates"]:
                candidate = by_name[result["candidate"]]
                score = result["aggregate"]
                writer.writerow([
                    outer["holdout_subject"], result["candidate"], candidate["feature_set"],
                    score["macro_f1"], score["minimum_class_recall"], score["accuracy"],
                    result["candidate"] == outer["selected_candidate"],
                ])

    card = f"""# BEHAVE relation v2 model card

## Nested evaluation

Every outer fold freezes one complete participant. Candidate selection happens only in a 3-fold GroupCV over the remaining participants. The outer participant is evaluated once after selection. The fixed selection order is macro-F1, minimum class recall, accuracy, then lower predefined complexity rank.

## Result

- Nested LOSO accuracy: **{aggregate['accuracy']:.4f}**
- Nested LOSO macro-F1: **{aggregate['macro_f1']:.4f}**
- Minimum aggregate class recall: **{aggregate['minimum_class_recall']:.4f}**
- Per-class recall: {json.dumps(aggregate['per_class_recall'])}
- Quality gate: **{summary['quality_gate']['status'].upper()}**
- v1 macro-F1: {v1['macro_f1']:.4f}; delta: {summary['comparison_to_v1']['macro_f1_delta']:+.4f}
- v1 minimum recall: {v1_min_recall:.4f}; delta: {summary['comparison_to_v1']['minimum_class_recall_delta']:+.4f}
- Deployment candidate under the predeclared replacement rule: **{replacement.upper()}**

## Temporal feature ablation

The temporal representation adds causal 15-frame rolling statistics for joint angular speed, person-object relative velocity, and object angular velocity. `ablation_summary.csv` records every inner-only comparison; no candidate is selected from outer test performance.

## License boundary

BEHAVE permits non-commercial scientific research. Raw fits are excluded from Git. The fitted `model.joblib` remains local and Git-ignored pending clarification of derived-weight redistribution.

## Limitations

{chr(10).join('- ' + value for value in summary['limitations'])}
"""
    (output / "model_card.md").write_text(card, encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
