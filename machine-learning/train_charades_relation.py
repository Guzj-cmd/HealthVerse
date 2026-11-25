"""Train a subject-disjoint Charades human-environment relation head.

The source data are real indoor videos. This script consumes the official
AllenAI RGB fc7 archive without extracting millions of small text files,
pools each video to mean/max features, tunes only inside the official train
subjects, and evaluates the untouched official test subjects once.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import tarfile
import time
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
from sklearn.base import clone
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_recall_fscore_support,
)
from sklearn.model_selection import GroupKFold
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


FEATURE_PATH = re.compile(
    r"(?:^|/)Charades_v1_features_rgb/(?P<video>[A-Z0-9]+)/"
    r"(?P=video)-(?P<frame>\d+)\.txt$"
)


@dataclass(frozen=True)
class AnnotationTable:
    ids: np.ndarray
    subjects: np.ndarray
    labels: np.ndarray
    scenes: np.ndarray


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_action_ids(value: str) -> set[str]:
    return {
        item.split()[0]
        for item in value.split(";")
        if item.strip() and item.split()
    }


def relation_vector(action_ids: set[str], relations: dict[str, list[str]]) -> np.ndarray:
    return np.asarray(
        [bool(action_ids.intersection(source_ids)) for source_ids in relations.values()],
        dtype=np.int8,
    )


def load_annotations(
    csv_path: Path, relations: dict[str, list[str]]
) -> AnnotationTable:
    rows: list[dict[str, str]] = []
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows.extend(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"no annotations in {csv_path}")
    ids = np.asarray([row["id"] for row in rows])
    if np.unique(ids).size != ids.size:
        raise ValueError(f"duplicate video ID in {csv_path}")
    return AnnotationTable(
        ids=ids,
        subjects=np.asarray([row["subject"] for row in rows]),
        labels=np.vstack([
            relation_vector(parse_action_ids(row["actions"]), relations)
            for row in rows
        ]),
        scenes=np.asarray([row["scene"] for row in rows]),
    )


def validate_official_split(train: AnnotationTable, test: AnnotationTable) -> None:
    overlap_ids = set(train.ids).intersection(test.ids)
    overlap_subjects = set(train.subjects).intersection(test.subjects)
    if overlap_ids:
        raise ValueError(f"official splits share {len(overlap_ids)} video IDs")
    if overlap_subjects:
        raise ValueError(
            f"official splits share {len(overlap_subjects)} subject IDs"
        )


def _flush_video(
    video_id: str | None,
    total: np.ndarray | None,
    maximum: np.ndarray | None,
    count: int,
    ids: list[str],
    pooled: list[np.ndarray],
) -> None:
    if video_id is None or total is None or maximum is None or count <= 0:
        return
    ids.append(video_id)
    pooled.append(np.concatenate([total / count, maximum]).astype(np.float32))


def pool_official_fc7_archive(
    archive: Path, output: Path, frame_stride: int = 6
) -> dict:
    """Stream the official tar.gz and save per-video mean/max fc7 features."""
    if frame_stride < 1:
        raise ValueError("frame_stride must be positive")
    ids: list[str] = []
    pooled: list[np.ndarray] = []
    seen: set[str] = set()
    current_id: str | None = None
    total: np.ndarray | None = None
    maximum: np.ndarray | None = None
    count = 0
    source_frame_count = 0
    used_frame_count = 0
    started = time.monotonic()

    with tarfile.open(archive, mode="r|gz") as tar:
        for member in tar:
            if not member.isfile():
                continue
            match = FEATURE_PATH.search(member.name)
            if not match:
                continue
            video_id = match.group("video")
            if current_id != video_id:
                _flush_video(current_id, total, maximum, count, ids, pooled)
                if video_id in seen:
                    raise ValueError(
                        "archive is not grouped by video; refusing ambiguous streaming pool"
                    )
                seen.add(video_id)
                current_id = video_id
                total = np.zeros(4096, dtype=np.float64)
                maximum = np.full(4096, -np.inf, dtype=np.float32)
                count = 0
            source_frame_count += 1
            # Official features are every fourth 24-fps frame (6 fps). Taking
            # every sixth official vector yields about one real observation per
            # second, close to the paper's 30-equidistant-frame RGB baseline.
            official_ordinal = (int(match.group("frame")) - 1) // 4
            if source_frame_count % 100_000 == 0:
                elapsed = max(0.001, time.monotonic() - started)
                print(
                    f"archive_frames={source_frame_count} pooled_frames={used_frame_count} "
                    f"videos={len(ids)} archive_frames_per_second="
                    f"{source_frame_count / elapsed:.1f}",
                    flush=True,
                )
            if official_ordinal % frame_stride != 0:
                continue
            extracted = tar.extractfile(member)
            if extracted is None:
                raise ValueError(f"cannot extract {member.name}")
            values = np.fromstring(extracted.read().decode("ascii"), sep=" ", dtype=np.float32)
            if values.shape != (4096,) or not np.isfinite(values).all():
                raise ValueError(f"invalid fc7 vector in {member.name}: {values.shape}")
            total += values
            maximum = np.maximum(maximum, values)
            count += 1
            used_frame_count += 1
    _flush_video(current_id, total, maximum, count, ids, pooled)
    if not pooled:
        raise ValueError("official archive contained no recognized fc7 features")
    features = np.vstack(pooled).astype(np.float32)
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output, ids=np.asarray(ids), features=features)
    return {
        "videos": len(ids),
        "archive_frames": source_frame_count,
        "pooled_frames": used_frame_count,
        "frame_stride": frame_stride,
        "dimensions": int(features.shape[1]),
    }


def load_feature_cache(path: Path) -> tuple[np.ndarray, np.ndarray]:
    with np.load(path, allow_pickle=False) as bundle:
        ids = np.asarray(bundle["ids"])
        features = np.asarray(bundle["features"], dtype=np.float32)
    if features.ndim != 2 or features.shape[1] != 8192:
        raise ValueError(f"unexpected pooled feature shape {features.shape}")
    if ids.size != features.shape[0] or np.unique(ids).size != ids.size:
        raise ValueError("pooled feature IDs are missing or duplicated")
    if not np.isfinite(features).all():
        raise ValueError("pooled features contain non-finite values")
    return ids, features


def align_features(
    table: AnnotationTable, feature_ids: np.ndarray, features: np.ndarray
) -> np.ndarray:
    index = {str(video_id): row for row, video_id in enumerate(feature_ids)}
    missing = [str(video_id) for video_id in table.ids if str(video_id) not in index]
    if missing:
        raise ValueError(f"missing {len(missing)} annotated videos, first={missing[0]}")
    return features[[index[str(video_id)] for video_id in table.ids]]


def build_estimator(alpha: float, random_seed: int) -> Pipeline:
    return Pipeline([
        ("scale", StandardScaler()),
        (
            "classifier",
            OneVsRestClassifier(
                SGDClassifier(
                    loss="log_loss",
                    penalty="l2",
                    alpha=alpha,
                    class_weight="balanced",
                    max_iter=2000,
                    tol=1e-4,
                    average=True,
                    random_state=random_seed,
                ),
                n_jobs=-1,
            ),
        ),
    ])


def macro_average_precision(y_true: np.ndarray, probabilities: np.ndarray) -> float:
    return float(np.mean([
        average_precision_score(y_true[:, column], probabilities[:, column])
        for column in range(y_true.shape[1])
    ]))


def per_class_average_precision(
    y_true: np.ndarray, probabilities: np.ndarray, names: list[str]
) -> dict[str, float]:
    return {
        name: float(average_precision_score(y_true[:, column], probabilities[:, column]))
        for column, name in enumerate(names)
    }


def choose_thresholds(y_true: np.ndarray, probabilities: np.ndarray) -> np.ndarray:
    grid = np.linspace(0.05, 0.95, 91)
    thresholds = np.zeros(y_true.shape[1], dtype=np.float64)
    for column in range(y_true.shape[1]):
        scores = [
            f1_score(
                y_true[:, column],
                probabilities[:, column] >= threshold,
                zero_division=0,
            )
            for threshold in grid
        ]
        thresholds[column] = grid[int(np.argmax(scores))]
    return thresholds


def expected_calibration_error(
    y_true: np.ndarray, probabilities: np.ndarray, bins: int = 10
) -> float:
    values: list[float] = []
    edges = np.linspace(0.0, 1.0, bins + 1)
    for column in range(y_true.shape[1]):
        error = 0.0
        scores = probabilities[:, column]
        targets = y_true[:, column]
        for lower, upper in zip(edges[:-1], edges[1:]):
            mask = (scores >= lower) & (scores < upper if upper < 1.0 else scores <= upper)
            if mask.any():
                error += float(mask.mean()) * abs(float(scores[mask].mean()) - float(targets[mask].mean()))
        values.append(error)
    return float(np.mean(values))


def evaluate(
    y_true: np.ndarray,
    probabilities: np.ndarray,
    thresholds: np.ndarray,
    names: list[str],
) -> dict:
    predicted = probabilities >= thresholds
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true,
        predicted,
        average=None,
        zero_division=0,
    )
    return {
        "macro_map": macro_average_precision(y_true, probabilities),
        "macro_f1": float(f1_score(y_true, predicted, average="macro", zero_division=0)),
        "macro_ece": expected_calibration_error(y_true, probabilities),
        "per_class_ap": per_class_average_precision(y_true, probabilities, names),
        "per_class_precision": {name: float(value) for name, value in zip(names, precision)},
        "per_class_recall": {name: float(value) for name, value in zip(names, recall)},
        "per_class_f1": {name: float(value) for name, value in zip(names, f1)},
        "support": {name: int(value) for name, value in zip(names, support)},
        "prevalence": {
            name: float(y_true[:, column].mean())
            for column, name in enumerate(names)
        },
    }


def tune_with_group_cv(
    x: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    names: list[str],
    alphas: list[float],
    folds: int,
    random_seed: int,
) -> tuple[float, np.ndarray, np.ndarray, list[dict]]:
    splitter = GroupKFold(n_splits=folds)
    candidates: list[dict] = []
    best_alpha = alphas[0]
    best_score = -np.inf
    best_oof: np.ndarray | None = None
    best_fold_records: list[dict] = []
    for alpha_index, alpha in enumerate(alphas):
        oof = np.zeros_like(y, dtype=np.float64)
        fold_records: list[dict] = []
        for fold_index, (fit, validation) in enumerate(splitter.split(x, y, groups)):
            model = build_estimator(alpha, random_seed + alpha_index * 100 + fold_index)
            model.fit(x[fit], y[fit])
            probabilities = model.predict_proba(x[validation])
            oof[validation] = probabilities
            fold_records.append({
                "fold": fold_index,
                "alpha": alpha,
                "train_subjects": int(np.unique(groups[fit]).size),
                "validation_subjects": int(np.unique(groups[validation]).size),
                "train_videos": int(fit.size),
                "validation_videos": int(validation.size),
                "macro_map": macro_average_precision(y[validation], probabilities),
                "per_class_ap": per_class_average_precision(y[validation], probabilities, names),
            })
        score = macro_average_precision(y, oof)
        candidates.append({"alpha": alpha, "oof_macro_map": score})
        if score > best_score:
            best_score = score
            best_alpha = alpha
            best_oof = oof
            best_fold_records = fold_records
    if best_oof is None:
        raise RuntimeError("grouped tuning produced no predictions")
    return best_alpha, best_oof, choose_thresholds(y, best_oof), candidates + best_fold_records


def gate_failures(metrics: dict, gate: dict) -> list[str]:
    failures: list[str] = []
    if metrics["macro_map"] < float(gate["minimum_macro_map"]):
        failures.append("macro mAP below minimum")
    if metrics["macro_f1"] < float(gate["minimum_macro_f1"]):
        failures.append("macro F1 below minimum")
    for name, value in metrics["per_class_ap"].items():
        required = metrics["prevalence"][name] + float(gate["minimum_ap_above_prevalence"])
        if value < required:
            failures.append(f"{name} AP {value:.6f} below prevalence+margin {required:.6f}")
    for name, value in metrics["per_class_recall"].items():
        if value < float(gate["minimum_class_recall"]):
            failures.append(f"{name} recall {value:.6f} below minimum")
    return failures


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def write_model_card(path: Path, metrics: dict) -> None:
    test = metrics["official_test_evaluated_once"]
    per_class = "\n".join(
        f"| {name} | {test['per_class_ap'][name]:.4f} | "
        f"{test['per_class_recall'][name]:.4f} | {test['support'][name]} |"
        for name in test["per_class_ap"]
    )
    failures = metrics["gate_failures"]
    failure_text = "None." if not failures else "\n".join(f"- {item}" for item in failures)
    text = f"""# Charades relation head model card

## Intended use

Research-only auxiliary recognition of seven observable human-environment
relations in indoor videos. It is not a medical model, ergonomic diagnosis,
or direct advice generator.

## Real-data protocol

- Source: official Charades v1 RGB two-stream fc7 features.
- Official train: {metrics['dataset']['train_videos']} videos / {metrics['dataset']['train_subjects']} subjects.
- Official test: {metrics['dataset']['test_videos']} videos / {metrics['dataset']['test_subjects']} subjects.
- Subject overlap: {metrics['dataset']['subject_overlap']}.
- Hyperparameters and thresholds were selected using grouped folds inside the
  official train split. The official test split was evaluated once.

## Results

- Gate: **{metrics['gate_status']}**
- Official-test macro mAP: {test['macro_map']:.6f}
- Official-test macro F1: {test['macro_f1']:.6f}
- Official-test macro ECE: {test['macro_ece']:.6f}

| Relation | AP | Recall | Positive videos |
|---|---:|---:|---:|
{per_class}

## Gate failures

{failure_text}

## License and privacy

The source archive is not redistributed. The AllenAI license permits
non-commercial research but forbids third-party redistribution of the data.
The local model artifact and video-level predictions remain Git-ignored by
default pending a separate derived-artifact license decision.
"""
    path.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("machine-learning/datasets/charades-relation.json"),
    )
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--rebuild-feature-cache", action="store_true")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    config_path = args.config if args.config.is_absolute() else repo_root / args.config
    config = load_json(config_path)
    cache = args.cache_dir.resolve()
    archive = cache / config["source_files"]["rgb_features"]["filename"]
    annotations = cache / "annotations" / "Charades"
    pooled_path = cache / "charades_rgb_fc7_mean_max.npz"
    if not archive.is_file():
        raise FileNotFoundError(f"official RGB feature archive not found: {archive}")
    if args.rebuild_feature_cache or not pooled_path.is_file():
        pool_official_fc7_archive(
            archive,
            pooled_path,
            int(config["training"]["feature_sampling_stride"]),
        )

    train = load_annotations(annotations / "Charades_v1_train.csv", config["relations"])
    test = load_annotations(annotations / "Charades_v1_test.csv", config["relations"])
    validate_official_split(train, test)
    feature_ids, pooled = load_feature_cache(pooled_path)
    x_train = align_features(train, feature_ids, pooled)
    x_test = align_features(test, feature_ids, pooled)
    names = list(config["relations"])

    best_alpha, oof, thresholds, tuning_records = tune_with_group_cv(
        x_train,
        train.labels,
        train.subjects,
        names,
        [float(value) for value in config["training"]["alpha_candidates"]],
        int(config["training"]["group_folds"]),
        int(config["random_seed"]),
    )
    oof_metrics = evaluate(train.labels, oof, thresholds, names)
    final_model = build_estimator(best_alpha, int(config["random_seed"]))
    final_model.fit(x_train, train.labels)
    test_probabilities = final_model.predict_proba(x_test)
    test_metrics = evaluate(test.labels, test_probabilities, thresholds, names)
    failures = gate_failures(test_metrics, config["quality_gate"])

    output = repo_root / config["output_dir"]
    output.mkdir(parents=True, exist_ok=True)
    archive_hash = sha256(archive)
    metrics = {
        "dataset": {
            "id": config["dataset_id"],
            "source_url": config["source_url"],
            "license": config["license"],
            "raw_data_redistributed": False,
            "feature_archive_bytes": archive.stat().st_size,
            "feature_archive_sha256": archive_hash,
            "train_videos": int(train.ids.size),
            "test_videos": int(test.ids.size),
            "train_subjects": int(np.unique(train.subjects).size),
            "test_subjects": int(np.unique(test.subjects).size),
            "subject_overlap": 0,
        },
        "feature_contract": {
            "source": "official RGB two-stream VGG-16 fc7 after ReLU",
            "pooling": "per-video mean concatenated with per-video maximum",
            "sampling": (
                "every sixth official 6-fps fc7 vector (approximately one "
                "real frame per second)"
            ),
            "dimensions": int(x_train.shape[1]),
        },
        "protocol": config["evaluation"],
        "selected_alpha": best_alpha,
        "thresholds_from_train_oof_only": {
            name: float(value) for name, value in zip(names, thresholds)
        },
        "train_oof": oof_metrics,
        "official_test_evaluated_once": test_metrics,
        "quality_gate": config["quality_gate"],
        "gate_status": "PASSED" if not failures else "REJECTED",
        "gate_failures": failures,
    }
    write_json(output / "metrics.json", metrics)
    write_json(output / "fold_history.json", tuning_records)
    write_json(output / "relation_mapping.json", config["relations"])
    write_model_card(output / "MODEL_CARD.md", metrics)

    with (output / "official_test_predictions.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow(["video_id", "subject", *[f"p_{name}" for name in names]])
        for video_id, subject, probabilities in zip(
            test.ids, test.subjects, test_probabilities
        ):
            writer.writerow([video_id, subject, *[f"{value:.9f}" for value in probabilities]])

    artifact = output / "model.joblib"
    joblib.dump(
        {
            "model": final_model,
            "labels": names,
            "thresholds": thresholds,
            "feature_contract": metrics["feature_contract"],
            "source_archive_sha256": archive_hash,
            "gate_status": metrics["gate_status"],
        },
        artifact,
    )
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
