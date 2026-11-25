"""Evaluate Charades relation recognition under joint subject/scene holdout.

This script only uses the official Charades training split.  Each outer fold
holds out one of the five largest scenes and removes every held-out subject
from training as well.  The official test split is never loaded.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import average_precision_score, recall_score
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def parse_actions(value: str) -> set[str]:
    return {item.split()[0] for item in value.split(";") if item.strip()}


def relation_vector(actions: set[str], relations: dict[str, list[str]]) -> list[int]:
    return [int(bool(actions.intersection(ids))) for ids in relations.values()]


def build_model(seed: int) -> Pipeline:
    return Pipeline(
        [
            ("scale", StandardScaler()),
            (
                "classifier",
                OneVsRestClassifier(
                    SGDClassifier(
                        loss="log_loss",
                        penalty="l2",
                        alpha=0.001,
                        class_weight="balanced",
                        max_iter=2000,
                        tol=1e-4,
                        average=True,
                        random_state=seed,
                    ),
                    n_jobs=-1,
                ),
            ),
        ]
    )


def evaluate(y: np.ndarray, probability: np.ndarray, names: list[str]) -> dict:
    per_ap: dict[str, float | None] = {}
    per_recall: dict[str, float | None] = {}
    prevalence: dict[str, float] = {}
    supported: list[float] = []
    for column, name in enumerate(names):
        target = y[:, column]
        prevalence[name] = float(target.mean())
        if np.unique(target).size < 2:
            per_ap[name] = None
            per_recall[name] = None
            continue
        ap = float(average_precision_score(target, probability[:, column]))
        recall = float(recall_score(target, probability[:, column] >= 0.5, zero_division=0))
        per_ap[name] = ap
        per_recall[name] = recall
        supported.append(ap)
    return {
        "macro_map_supported": float(np.mean(supported)) if supported else None,
        "supported_classes": len(supported),
        "per_class_ap": per_ap,
        "per_class_recall_at_0_5": per_recall,
        "prevalence": prevalence,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    relations = config["relations"]
    names = list(relations)
    with args.annotations.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    with np.load(args.features, allow_pickle=False) as bundle:
        feature_ids = np.asarray(bundle["ids"]).astype(str)
        features = np.asarray(bundle["features"], dtype=np.float32)
    index = {video_id: row for row, video_id in enumerate(feature_ids)}
    missing = [row["id"] for row in rows if row["id"] not in index]
    if missing:
        raise ValueError(f"missing {len(missing)} train videos; first={missing[0]}")

    ids = np.asarray([row["id"] for row in rows])
    subjects = np.asarray([row["subject"] for row in rows])
    scenes = np.asarray([row["scene"] for row in rows])
    y = np.asarray(
        [relation_vector(parse_actions(row["actions"]), relations) for row in rows],
        dtype=np.int8,
    )
    x = features[[index[video_id] for video_id in ids]]
    held_scenes = [name for name, _ in Counter(scenes).most_common(5)]

    folds: list[dict] = []
    all_y: list[np.ndarray] = []
    all_probability: list[np.ndarray] = []
    for fold_index, scene in enumerate(held_scenes):
        test_mask = scenes == scene
        test_subjects = set(subjects[test_mask])
        train_mask = (~test_mask) & np.asarray([subject not in test_subjects for subject in subjects])
        overlap = set(subjects[train_mask]).intersection(test_subjects)
        if overlap:
            raise AssertionError(f"subject leakage in {scene}: {sorted(overlap)[:3]}")
        model = build_model(20261125 + fold_index)
        model.fit(x[train_mask], y[train_mask])
        probability = model.predict_proba(x[test_mask])
        metrics = evaluate(y[test_mask], probability, names)
        folds.append(
            {
                "held_out_scene": scene,
                "train_videos": int(train_mask.sum()),
                "test_videos": int(test_mask.sum()),
                "train_subjects": int(np.unique(subjects[train_mask]).size),
                "test_subjects": int(np.unique(subjects[test_mask]).size),
                "subject_overlap": 0,
                "metrics": metrics,
            }
        )
        all_y.append(y[test_mask])
        all_probability.append(probability)

    aggregate = evaluate(np.vstack(all_y), np.vstack(all_probability), names)
    thresholds = {
        "minimum_aggregate_macro_map": 0.35,
        "minimum_each_scene_macro_map_supported": 0.25,
        "minimum_supported_classes_per_scene": 4,
    }
    failures: list[str] = []
    if aggregate["macro_map_supported"] is None or aggregate["macro_map_supported"] < 0.35:
        failures.append("aggregate macro-mAP below 0.35")
    for fold in folds:
        metric = fold["metrics"]
        if metric["supported_classes"] < 4:
            failures.append(f"{fold['held_out_scene']}: fewer than four supported classes")
        if metric["macro_map_supported"] is None or metric["macro_map_supported"] < 0.25:
            failures.append(f"{fold['held_out_scene']}: macro-mAP below 0.25")

    result = {
        "protocol": {
            "source_split": "official Charades train only; official test not loaded",
            "outer": "leave one of the five largest scenes out and remove all test subjects from training",
            "model": "fixed alpha=0.001 class-balanced one-vs-rest logistic SGD",
            "primary_metric": "macro average precision over classes with both labels in the held-out scene",
        },
        "data": {
            "videos": int(ids.size),
            "subjects": int(np.unique(subjects).size),
            "scenes": int(np.unique(scenes).size),
            "held_out_scenes": held_scenes,
            "relations": names,
        },
        "folds": folds,
        "aggregate": aggregate,
        "quality_gate": {
            "thresholds": thresholds,
            "status": "PASSED" if not failures else "REJECTED",
            "failures": failures,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["quality_gate"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

