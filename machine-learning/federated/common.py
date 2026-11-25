from __future__ import annotations

import hashlib
import hmac
import json
import math
import platform
import uuid
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class Dataset:
    x: np.ndarray
    y: np.ndarray
    subjects: np.ndarray
    labels: list[str]


def pose_features(landmarks: list[dict[str, float]]) -> np.ndarray:
    xyz = np.asarray([[p["x"], p["y"], p["z"]] for p in landmarks], dtype=np.float64)
    if xyz.shape != (33, 3) or not np.isfinite(xyz).all():
        raise ValueError("expected 33 finite MediaPipe xyz landmarks")
    hip = (xyz[23] + xyz[24]) / 2
    shoulder = (xyz[11] + xyz[12]) / 2
    scale = max(float(np.linalg.norm(shoulder - hip)), float(np.linalg.norm(xyz[11] - xyz[12])), 1e-6)
    return ((xyz - hip) / scale).reshape(-1).astype(np.float32)


def load_jsonl(path: str | Path) -> Dataset:
    rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    labels = sorted({str(row["label"]) for row in rows})
    lookup = {name: index for index, name in enumerate(labels)}
    return Dataset(
        x=np.vstack([pose_features(row["landmarks"]) for row in rows]),
        y=np.asarray([lookup[str(row["label"])] for row in rows], dtype=np.int64),
        subjects=np.asarray([str(row["subject_id"]) for row in rows]),
        labels=labels,
    )


def split_subjects(subjects: np.ndarray, seed: int, train_n: int, val_n: int) -> dict[str, list[str]]:
    unique = np.unique(subjects).tolist()
    rng = np.random.default_rng(seed)
    rng.shuffle(unique)
    if train_n + val_n >= len(unique):
        raise ValueError("split must leave at least one test subject")
    return {"train": unique[:train_n], "validation": unique[train_n:train_n + val_n], "test": unique[train_n + val_n:]}


def init_model(input_dim: int, hidden_dim: int, classes: int, seed: int) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    return {
        "w1": (rng.normal(0, math.sqrt(2 / input_dim), (input_dim, hidden_dim))).astype(np.float64),
        "b1": np.zeros(hidden_dim, dtype=np.float64),
        "w2": (rng.normal(0, math.sqrt(2 / hidden_dim), (hidden_dim, classes))).astype(np.float64),
        "b2": np.zeros(classes, dtype=np.float64),
    }


def clone_model(model: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    return {key: value.copy() for key, value in model.items()}


def predict_proba(model: dict[str, np.ndarray], x: np.ndarray) -> np.ndarray:
    hidden = np.maximum(0, x @ model["w1"] + model["b1"])
    logits = hidden @ model["w2"] + model["b2"]
    logits -= logits.max(axis=1, keepdims=True)
    exp = np.exp(logits)
    return exp / exp.sum(axis=1, keepdims=True)


def local_train(model: dict[str, np.ndarray], x: np.ndarray, y: np.ndarray, *, epochs: int, lr: float,
                batch_size: int, seed: int, weight_decay: float = 1e-4,
                class_balance: bool = False) -> dict[str, np.ndarray]:
    current = clone_model(model)
    rng = np.random.default_rng(seed)
    classes = current["b2"].size
    counts = np.bincount(y, minlength=classes).astype(np.float64)
    if class_balance:
        weights = np.zeros(classes, dtype=np.float64)
        present = counts > 0
        weights[present] = len(y) / (classes * counts[present])
    else:
        weights = np.ones(classes)
    for _ in range(epochs):
        order = rng.permutation(len(x))
        for start in range(0, len(x), batch_size):
            idx = order[start:start + batch_size]
            xb, yb = x[idx], y[idx]
            z1 = xb @ current["w1"] + current["b1"]
            h = np.maximum(0, z1)
            logits = h @ current["w2"] + current["b2"]
            logits -= logits.max(axis=1, keepdims=True)
            prob = np.exp(logits); prob /= prob.sum(axis=1, keepdims=True)
            grad_logits = prob
            grad_logits[np.arange(len(idx)), yb] -= 1
            grad_logits *= weights[yb, None]
            grad_logits /= max(float(weights[yb].sum()), 1e-12)
            gw2 = h.T @ grad_logits + weight_decay * current["w2"]
            gb2 = grad_logits.sum(axis=0)
            gh = grad_logits @ current["w2"].T
            gh[z1 <= 0] = 0
            gw1 = xb.T @ gh + weight_decay * current["w1"]
            gb1 = gh.sum(axis=0)
            for key, grad in (("w1", gw1), ("b1", gb1), ("w2", gw2), ("b2", gb2)):
                current[key] -= lr * grad
    return current


def delta(new: dict[str, np.ndarray], old: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    return {key: new[key] - old[key] for key in old}


def clip_update(update: dict[str, np.ndarray], max_norm: float) -> tuple[dict[str, np.ndarray], float, float]:
    norm = math.sqrt(sum(float(np.sum(value * value)) for value in update.values()))
    factor = min(1.0, max_norm / max(norm, 1e-12))
    return {key: value * factor for key, value in update.items()}, norm, factor


def aggregate(model: dict[str, np.ndarray], updates: list[tuple[int, dict[str, np.ndarray]]], noise_std: float = 0.0,
              seed: int = 0) -> dict[str, np.ndarray]:
    total = sum(count for count, _ in updates)
    result = clone_model(model)
    rng = np.random.default_rng(seed)
    for key in result:
        mean = sum(count * update[key] for count, update in updates) / total
        if noise_std > 0:
            mean = mean + rng.normal(0, noise_std, mean.shape)
        result[key] += mean
    return result


def model_to_json(model: dict[str, np.ndarray]) -> dict[str, list]:
    return {key: value.tolist() for key, value in model.items()}


def model_from_json(value: dict[str, list]) -> dict[str, np.ndarray]:
    return {key: np.asarray(array, dtype=np.float64) for key, array in value.items()}


def classification_metrics(y: np.ndarray, pred: np.ndarray, labels: list[str]) -> dict:
    recalls, f1s, confusion = {}, [], np.zeros((len(labels), len(labels)), dtype=int)
    for actual, guessed in zip(y, pred): confusion[actual, guessed] += 1
    for i, label in enumerate(labels):
        tp = confusion[i, i]; fn = confusion[i].sum() - tp; fp = confusion[:, i].sum() - tp
        recall = float(tp / (tp + fn)) if tp + fn else 0.0
        precision = float(tp / (tp + fp)) if tp + fp else 0.0
        recalls[label] = recall
        f1s.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return {"samples": int(len(y)), "accuracy": float(np.mean(y == pred)), "macro_f1": float(np.mean(f1s)),
            "per_class_recall": recalls, "confusion_matrix": confusion.tolist()}


def device_fingerprint(secret: str) -> str:
    raw = f"{platform.node()}|{uuid.getnode()}|{platform.system()}".encode()
    return hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


def sign_body(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

