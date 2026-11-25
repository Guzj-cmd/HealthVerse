"""Source-scene specialist ensemble with source-only weight selection.

For every frozen outer target scene, independent experts are trained on the
five largest remaining source scenes.  Expert weights are proportional to the
expert's macro-mAP on the other source scenes.  Target-scene labels are only
read after weights are frozen for final evaluation.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sklearn.linear_model import SGDClassifier
from sklearn.preprocessing import StandardScaler, normalize

from run_scene_generalization import evaluate, parse_actions, relation_vector


@dataclass
class Specialist:
    scaler: StandardScaler
    classifiers: list[SGDClassifier | float]


def fit_specialist(x: np.ndarray, y: np.ndarray, seed: int) -> Specialist:
    x_norm = normalize(x, norm="l2", copy=True)
    scaler = StandardScaler()
    x_scaled = scaler.fit_transform(x_norm)
    classifiers: list[SGDClassifier | float] = []
    for column in range(y.shape[1]):
        target = y[:, column]
        if np.unique(target).size < 2:
            # Laplace-smoothed source-scene prevalence, not a target-derived value.
            classifiers.append(float((target.sum() + 1) / (target.size + 2)))
            continue
        classifier = SGDClassifier(
            loss="log_loss",
            penalty="l2",
            alpha=0.001,
            class_weight="balanced",
            max_iter=2000,
            tol=1e-4,
            average=True,
            random_state=seed + column,
        )
        classifier.fit(x_scaled, target)
        classifiers.append(classifier)
    return Specialist(scaler=scaler, classifiers=classifiers)


def predict(specialist: Specialist, x: np.ndarray) -> np.ndarray:
    x_scaled = specialist.scaler.transform(normalize(x, norm="l2", copy=True))
    probability = np.zeros((x.shape[0], len(specialist.classifiers)), dtype=np.float64)
    for column, classifier in enumerate(specialist.classifiers):
        if isinstance(classifier, float):
            probability[:, column] = classifier
        else:
            probability[:, column] = classifier.predict_proba(x_scaled)[:, 1]
    return probability


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    relations = config["relations"]
    names = list(relations)
    with args.annotations.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    with np.load(args.features, allow_pickle=False) as bundle:
        feature_ids = np.asarray(bundle["ids"]).astype(str)
        feature_matrix = np.asarray(bundle["features"], dtype=np.float32)
    index = {video_id: row for row, video_id in enumerate(feature_ids)}
    ids = np.asarray([row["id"] for row in rows])
    subjects = np.asarray([row["subject"] for row in rows])
    scenes = np.asarray([row["scene"] for row in rows])
    y = np.asarray(
        [relation_vector(parse_actions(row["actions"]), relations) for row in rows], dtype=np.int8
    )
    x = feature_matrix[[index[video_id] for video_id in ids]]

    held_scenes = baseline["data"]["held_out_scenes"]
    folds: list[dict] = []
    aggregate_y: list[np.ndarray] = []
    aggregate_probability: list[np.ndarray] = []
    for outer_index, target_scene in enumerate(held_scenes):
        target_mask = scenes == target_scene
        target_subjects = set(subjects[target_mask])
        source_mask = (~target_mask) & np.asarray([subject not in target_subjects for subject in subjects])
        if set(subjects[source_mask]).intersection(target_subjects):
            raise AssertionError("outer subject leakage")
        source_scene_names = [
            scene for scene, _ in Counter(scenes[source_mask]).most_common(5)
        ]
        specialists: list[Specialist] = []
        source_scores: list[float] = []
        specialist_records: list[dict] = []
        for specialist_index, source_scene in enumerate(source_scene_names):
            train_mask = source_mask & (scenes == source_scene)
            validation_mask = source_mask & np.isin(scenes, [s for s in source_scene_names if s != source_scene])
            specialist = fit_specialist(x[train_mask], y[train_mask], 20261125 + outer_index * 100 + specialist_index * 10)
            validation_probability = predict(specialist, x[validation_mask])
            validation_metrics = evaluate(y[validation_mask], validation_probability, names)
            score = float(validation_metrics["macro_map_supported"] or 0.0)
            specialists.append(specialist)
            source_scores.append(max(score, 1e-6))
            specialist_records.append(
                {
                    "source_scene": source_scene,
                    "train_videos": int(train_mask.sum()),
                    "source_only_validation_videos": int(validation_mask.sum()),
                    "source_only_macro_map": score,
                }
            )
        weights = np.asarray(source_scores, dtype=np.float64)
        weights /= weights.sum()
        probability = np.zeros((int(target_mask.sum()), y.shape[1]), dtype=np.float64)
        for weight, specialist in zip(weights, specialists):
            probability += weight * predict(specialist, x[target_mask])
        target_metrics = evaluate(y[target_mask], probability, names)
        for record, weight in zip(specialist_records, weights):
            record["frozen_weight"] = float(weight)
        folds.append(
            {
                "held_out_scene": target_scene,
                "train_videos": int(source_mask.sum()),
                "test_videos": int(target_mask.sum()),
                "test_subjects": int(np.unique(subjects[target_mask]).size),
                "subject_overlap": 0,
                "specialists": specialist_records,
                "metrics": target_metrics,
            }
        )
        aggregate_y.append(y[target_mask])
        aggregate_probability.append(probability)

    aggregate = evaluate(np.vstack(aggregate_y), np.vstack(aggregate_probability), names)
    thresholds = baseline["quality_gate"]["thresholds"]
    failures: list[str] = []
    if aggregate["macro_map_supported"] is None or aggregate["macro_map_supported"] < thresholds["minimum_aggregate_macro_map"]:
        failures.append("aggregate macro-mAP below 0.35")
    for fold in folds:
        metric = fold["metrics"]
        if metric["supported_classes"] < thresholds["minimum_supported_classes_per_scene"]:
            failures.append(f"{fold['held_out_scene']}: fewer than four supported classes")
        if metric["macro_map_supported"] is None or metric["macro_map_supported"] < thresholds["minimum_each_scene_macro_map_supported"]:
            failures.append(f"{fold['held_out_scene']}: macro-mAP below 0.25")

    result = {
        "candidate": "independent source-scene specialists with source-only cross-scene mAP weighting",
        "source_split": "Charades official train only; official test not loaded",
        "weight_contract": "weights use predictions on other source scenes only; target labels do not participate",
        "held_out_scenes": held_scenes,
        "folds": folds,
        "aggregate": aggregate,
        "comparison": {
            "baseline_macro_map": baseline["aggregate"]["macro_map_supported"],
            "candidate_macro_map": aggregate["macro_map_supported"],
            "delta": aggregate["macro_map_supported"] - baseline["aggregate"]["macro_map_supported"],
        },
        "quality_gate": {
            "thresholds": thresholds,
            "status": "PASSED" if not failures else "REJECTED",
            "failures": failures,
        },
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"comparison": result["comparison"], "gate": result["quality_gate"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

