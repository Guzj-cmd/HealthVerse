from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, recall_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .features import pose_features, schema
from .io import PoseSample


def grouped_split(samples: list[PoseSample], config: dict) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(int(config["random_seed"]))
    groups = np.asarray([sample.subject_id for sample in samples])
    unique = np.unique(groups)
    if unique.size < 6:
        raise ValueError("at least 6 distinct subject_id groups are required for train/validation/test")
    rng.shuffle(unique)
    split = config["split"]
    train_count = max(1, int(round(unique.size * float(split["train_fraction"]))))
    validation_count = max(1, int(round(unique.size * float(split["validation_fraction"]))))
    if train_count + validation_count >= unique.size:
        train_count = unique.size - 2
        validation_count = 1
    group_sets = {
        "train": set(unique[:train_count]),
        "validation": set(unique[train_count:train_count + validation_count]),
        "test": set(unique[train_count + validation_count:]),
    }
    indices = {name: np.asarray([i for i, group in enumerate(groups) if group in members], dtype=int) for name, members in group_sets.items()}
    if any(values.size == 0 for values in indices.values()):
        raise ValueError("group split produced an empty partition")
    return indices


def candidate_models(config: dict) -> dict[str, object]:
    seed, models = int(config["random_seed"]), config["models"]
    lr = models["logistic_regression"]
    rf = models["random_forest"]
    hg = models["hist_gradient_boosting"]
    mlp = models["edusense_mlp"]
    return {
        "logistic_regression": make_pipeline(StandardScaler(), LogisticRegression(C=float(lr["C"]), max_iter=int(lr["max_iter"]), class_weight="balanced", random_state=seed)),
        "random_forest": RandomForestClassifier(n_estimators=int(rf["n_estimators"]), max_depth=int(rf["max_depth"]), min_samples_leaf=int(rf["min_samples_leaf"]), class_weight="balanced_subsample", n_jobs=-1, random_state=seed),
        "hist_gradient_boosting": HistGradientBoostingClassifier(max_iter=int(hg["max_iter"]), learning_rate=float(hg["learning_rate"]), max_leaf_nodes=int(hg["max_leaf_nodes"]), class_weight="balanced", random_state=seed),
        "edusense_mlp": make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=tuple(int(v) for v in mlp["hidden_layer_sizes"]), alpha=float(mlp["alpha"]), max_iter=int(mlp["max_iter"]), early_stopping=False, random_state=seed)),
    }


def matrix(samples: list[PoseSample]) -> tuple[np.ndarray, np.ndarray]:
    return np.vstack([pose_features(sample.landmarks) for sample in samples]), np.asarray([sample.label for sample in samples])


def metrics(y_true: np.ndarray, y_pred: np.ndarray, labels: list[str]) -> dict[str, object]:
    per_class = recall_score(y_true, y_pred, labels=labels, average=None, zero_division=0)
    return {
        "sample_count": int(len(y_true)),
        "class_support": {label: int(np.sum(y_true == label)) for label in labels},
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
        "per_class_recall": {label: float(value) for label, value in zip(labels, per_class)},
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
    }


def threshold_status(result: dict[str, object], thresholds: dict[str, float]) -> tuple[str, list[str]]:
    failures = []
    if result["accuracy"] < float(thresholds["accuracy"]):
        failures.append("accuracy")
    if result["macro_f1"] < float(thresholds["macro_f1"]):
        failures.append("macro_f1")
    low = [name for name, value in result["per_class_recall"].items() if value < float(thresholds["minimum_class_recall"])]
    if low:
        failures.append("class_recall:" + ",".join(low))
    minimum_support = int(thresholds.get("minimum_test_samples_per_class", 0))
    under_supported = [name for name, count in result.get("class_support", {}).items() if int(count) < minimum_support]
    if under_supported:
        failures.append("class_support:" + ",".join(under_supported))
    return ("passed" if not failures else "failed"), failures


def save_bundle(path: Path, model: object, labels: list[str], config: dict, metadata: dict) -> None:
    joblib.dump({"model": model, "labels": labels, "feature_schema": schema(), "config": config, "metadata": metadata}, path)


def load_config(path: str | Path) -> dict:
    with Path(path).open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)
