from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
from scipy.io import loadmat
from sklearn.base import clone
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support


WIDTH = 1280.0
HEIGHT = 720.0
CLASSES = ["empty", "standing_walking", "sitting", "talking"]
MAX_PERSONS = 4
FEATURE_NAMES = ["person_count"]
for slot in range(MAX_PERSONS):
    FEATURE_NAMES.extend([
        f"p{slot}_present", f"p{slot}_cx", f"p{slot}_cy", f"p{slot}_w",
        f"p{slot}_h", f"p{slot}_area", f"p{slot}_aspect", f"p{slot}_bottom",
    ])
for field in ("cx", "cy", "w", "h", "area", "aspect"):
    FEATURE_NAMES.extend([f"{field}_mean", f"{field}_min", f"{field}_max"])
FEATURE_NAMES.extend(["pair_distance_mean", "pair_iou_mean"])


@dataclass(frozen=True)
class OfficeSample:
    features: np.ndarray
    label: str
    subject_id: str
    day: int
    frame: int


def subject_for_day(day: int) -> str:
    if day <= 12:
        return "office-1-participant-1"
    if day <= 14:
        return "office-2-participant-2"
    if day <= 17:
        return "office-3-participant-3"
    return "office-4-participant-4"


def iou(first: np.ndarray, second: np.ndarray) -> float:
    x1 = max(first[0], second[0]); y1 = max(first[1], second[1])
    x2 = min(first[0] + first[2], second[0] + second[2])
    y2 = min(first[1] + first[3], second[1] + second[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = first[2] * first[3] + second[2] * second[3] - intersection
    return float(intersection / union) if union > 0 else 0.0


def frame_features(boxes: np.ndarray) -> np.ndarray:
    boxes = np.asarray(boxes, dtype=np.float64).reshape(-1, 4)
    valid = boxes[(boxes[:, 2] > 0) & (boxes[:, 3] > 0)]
    if valid.size:
        valid = valid[np.argsort(valid[:, 0])]
    rows: list[float] = [float(len(valid)) / float(MAX_PERSONS)]
    values: dict[str, list[float]] = {name: [] for name in ("cx", "cy", "w", "h", "area", "aspect")}
    normalized: list[np.ndarray] = []
    for box in valid[:MAX_PERSONS]:
        x, y, width, height = box
        nx, ny, nw, nh = x / WIDTH, y / HEIGHT, width / WIDTH, height / HEIGHT
        cx, cy = nx + nw / 2.0, ny + nh / 2.0
        area, aspect = nw * nh, nw / max(nh, 1e-9)
        rows.extend([1.0, cx, cy, nw, nh, area, aspect, ny + nh])
        values["cx"].append(cx); values["cy"].append(cy)
        values["w"].append(nw); values["h"].append(nh)
        values["area"].append(area); values["aspect"].append(aspect)
        normalized.append(np.asarray([nx, ny, nw, nh]))
    rows.extend([0.0] * (8 * (MAX_PERSONS - min(MAX_PERSONS, len(valid)))))
    for name in ("cx", "cy", "w", "h", "area", "aspect"):
        current = values[name]
        rows.extend([float(np.mean(current)), float(np.min(current)), float(np.max(current))] if current else [0.0, 0.0, 0.0])
    distances: list[float] = []
    overlaps: list[float] = []
    for first in range(len(normalized)):
        for second in range(first + 1, len(normalized)):
            a, b = normalized[first], normalized[second]
            ac = np.asarray([a[0] + a[2] / 2.0, a[1] + a[3] / 2.0])
            bc = np.asarray([b[0] + b[2] / 2.0, b[1] + b[3] / 2.0])
            distances.append(float(np.linalg.norm(ac - bc)))
            overlaps.append(iou(a, b))
    rows.extend([float(np.mean(distances)) if distances else 0.0, float(np.mean(overlaps)) if overlaps else 0.0])
    result = np.asarray(rows, dtype=np.float32)
    if result.shape != (len(FEATURE_NAMES),):
        raise AssertionError((result.shape, len(FEATURE_NAMES)))
    return result


def frame_label(labels: np.ndarray) -> str | None:
    labels = np.asarray(labels, dtype=int)
    active = labels[labels > 0]
    if np.any(active == 4):
        return None
    if active.size == 0:
        return "empty"
    if np.any(active == 3) or active.size > 1:
        return "talking"
    if active[0] == 1:
        return "standing_walking"
    if active[0] == 2:
        return "sitting"
    raise ValueError(f"unexpected labels: {active.tolist()}")


def load_dataset(gt_dir: Path) -> tuple[list[OfficeSample], dict]:
    samples: list[OfficeSample] = []
    excluded_falls: list[dict] = []
    day_counts: dict[str, Counter] = {}
    row_shape_counts: Counter = Counter()
    paths = sorted(gt_dir.glob("day*.mat"))
    if len(paths) != 20:
        raise ValueError(f"expected 20 ground-truth files, found {len(paths)}")
    for path in paths:
        day = int(path.stem[-2:])
        subject = subject_for_day(day)
        frames = loadmat(path, squeeze_me=True)["labels"]
        day_counts[str(day)] = Counter()
        for frame_index, raw in enumerate(frames):
            raw = np.asarray(raw, dtype=np.float64).reshape(-1, 5)
            row_shape_counts[str(raw.shape[0])] += 1
            labels = raw[:, 4].astype(int)
            if np.any(labels == 4):
                excluded_falls.append({"day": day, "frame": frame_index, "subject_id": subject})
                day_counts[str(day)]["fallen_excluded"] += 1
                continue
            label = frame_label(labels)
            assert label is not None
            samples.append(OfficeSample(frame_features(raw[:, :4]), label, subject, day, frame_index))
            day_counts[str(day)][label] += 1
    audit = {
        "source_files": len(paths),
        "included_frames": len(samples),
        "excluded_fallen_frames": len(excluded_falls),
        "excluded_fallen_subjects": sorted({item["subject_id"] for item in excluded_falls}),
        "annotation_row_counts": dict(row_shape_counts),
        "day_counts": {day: dict(counts) for day, counts in day_counts.items()},
    }
    return samples, audit


def candidates(seed: int) -> dict[str, object]:
    return {
        "extra_trees": ExtraTreesClassifier(
            n_estimators=80, min_samples_leaf=4, class_weight="balanced_subsample",
            n_jobs=-1, random_state=seed,
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=80, min_samples_leaf=4, max_features="sqrt",
            class_weight="balanced_subsample", n_jobs=-1, random_state=seed,
        ),
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            max_iter=90, learning_rate=0.08, max_leaf_nodes=31, l2_regularization=0.1,
            class_weight="balanced", random_state=seed,
        ),
    }


def indices_for(samples: list[OfficeSample], subjects: set[str]) -> np.ndarray:
    return np.asarray([index for index, sample in enumerate(samples) if sample.subject_id in subjects], dtype=int)


def capped_training_indices(
    samples: list[OfficeSample], subjects: set[str], cap_per_subject_class: int, seed: int
) -> np.ndarray:
    """Limit highly correlated 1 FPS frames without changing evaluation coverage."""
    rng = np.random.default_rng(seed)
    selected: list[int] = []
    for subject in sorted(subjects):
        for label in CLASSES:
            group = np.asarray([
                index for index, sample in enumerate(samples)
                if sample.subject_id == subject and sample.label == label
            ], dtype=int)
            if group.size > cap_per_subject_class:
                group = np.sort(rng.choice(group, size=cap_per_subject_class, replace=False))
            selected.extend(group.tolist())
    return np.asarray(sorted(selected), dtype=int)


def score_model(model: object, x: np.ndarray, y: np.ndarray, indices: np.ndarray) -> dict:
    prediction = model.predict(x[indices])
    return {
        "accuracy": float(accuracy_score(y[indices], prediction)),
        "macro_f1": float(f1_score(y[indices], prediction, labels=CLASSES, average="macro", zero_division=0)),
    }


def select_candidate(samples: list[OfficeSample], x: np.ndarray, y: np.ndarray, development: list[str], seed: int) -> tuple[str, list[dict]]:
    rows: list[dict] = []
    for name, prototype in candidates(seed).items():
        fold_scores: list[float] = []
        for validation_subject in development:
            train_subjects = set(development) - {validation_subject}
            train_idx = capped_training_indices(samples, train_subjects, 6000, seed)
            validation_idx = indices_for(samples, {validation_subject})
            model = clone(prototype).fit(x[train_idx], y[train_idx])
            score = score_model(model, x, y, validation_idx)
            fold_scores.append(score["macro_f1"])
            rows.append({"candidate": name, "validation_subject": validation_subject, **score})
        rows.append({
            "candidate": name,
            "validation_subject": "mean",
            "accuracy": float(np.mean([row["accuracy"] for row in rows if row["candidate"] == name and row["validation_subject"] != "mean"])),
            "macro_f1": float(np.mean(fold_scores)),
        })
    means = [row for row in rows if row["validation_subject"] == "mean"]
    selected = max(means, key=lambda row: (row["macro_f1"], row["accuracy"], row["candidate"]))["candidate"]
    return str(selected), rows


def class_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, dict[str, float | int]]:
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=CLASSES, zero_division=0
    )
    return {
        label: {"precision": float(precision[i]), "recall": float(recall[i]), "f1": float(f1[i]), "support": int(support[i])}
        for i, label in enumerate(CLASSES)
    }


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader(); writer.writerows(rows)


def train(gt_dir: Path, output: Path, seed: int) -> None:
    output.mkdir(parents=True, exist_ok=True)
    samples, audit = load_dataset(gt_dir)
    x = np.vstack([sample.features for sample in samples])
    y = np.asarray([sample.label for sample in samples])
    subjects = sorted({sample.subject_id for sample in samples})
    if len(subjects) != 4:
        raise ValueError(f"expected four participant/office groups, found {subjects}")

    outer_rows: list[dict] = []
    candidate_rows: list[dict] = []
    split_rows: list[dict] = []
    oof_prediction = np.empty(len(samples), dtype=object)
    for test_subject in subjects:
        development = [subject for subject in subjects if subject != test_subject]
        selected, inner = select_candidate(samples, x, y, development, seed)
        for row in inner:
            candidate_rows.append({"outer_test_subject": test_subject, **row})
        train_idx = capped_training_indices(samples, set(development), 10000, seed)
        test_idx = indices_for(samples, {test_subject})
        model = clone(candidates(seed)[selected]).fit(x[train_idx], y[train_idx])
        prediction = model.predict(x[test_idx])
        oof_prediction[test_idx] = prediction
        outer_rows.append({
            "test_subject": test_subject,
            "selected_candidate": selected,
            "train_frames": int(train_idx.size),
            "test_frames": int(test_idx.size),
            "accuracy": float(accuracy_score(y[test_idx], prediction)),
            "macro_f1": float(f1_score(y[test_idx], prediction, labels=CLASSES, average="macro", zero_division=0)),
        })
        for subject in subjects:
            days = sorted({sample.day for sample in samples if sample.subject_id == subject})
            split_rows.append({
                "outer_test_subject": test_subject,
                "subject_id": subject,
                "role": "test" if subject == test_subject else "development",
                "days": "|".join(map(str, days)),
                "frames": sum(sample.subject_id == subject for sample in samples),
            })

    overall = {
        "accuracy": float(accuracy_score(y, oof_prediction)),
        "macro_f1": float(f1_score(y, oof_prediction, labels=CLASSES, average="macro", zero_division=0)),
        "per_class": class_metrics(y, oof_prediction),
        "confusion_matrix_labels": CLASSES,
        "evaluation_protocol": "nested leave-one-participant-and-office-out",
        "subjects": subjects,
        "frames": len(samples),
    }
    thresholds = {"accuracy": 0.80, "macro_f1": 0.80, "minimum_class_recall": 0.50}
    failures: list[str] = []
    if overall["accuracy"] < thresholds["accuracy"]:
        failures.append(f"accuracy {overall['accuracy']:.6f} < {thresholds['accuracy']:.2f}")
    if overall["macro_f1"] < thresholds["macro_f1"]:
        failures.append(f"macro_f1 {overall['macro_f1']:.6f} < {thresholds['macro_f1']:.2f}")
    for label in CLASSES:
        recall = float(overall["per_class"][label]["recall"])
        if recall < thresholds["minimum_class_recall"]:
            failures.append(f"{label} recall {recall:.6f} < {thresholds['minimum_class_recall']:.2f}")
    overall["quality_gate"] = {
        "status": "ACCEPTED" if not failures else "REJECTED",
        "thresholds": thresholds,
        "failures": failures,
    }
    all_selected, full_candidate_rows = select_candidate(samples, x, y, subjects, seed)
    final_train_idx = capped_training_indices(samples, set(subjects), 20000, seed)
    if not failures:
        final_model = clone(candidates(seed)[all_selected]).fit(x[final_train_idx], y[final_train_idx])
        artifact = {
            "model": final_model,
            "feature_names": FEATURE_NAMES,
            "classes": CLASSES,
            "image_width": int(WIDTH),
            "image_height": int(HEIGHT),
            "dataset_id": "edinburgh-office-monitoring",
            "input_contract": "up to four person bounding boxes [x,y,width,height] from an upstream detector",
        }
        joblib.dump(artifact, output / "model.joblib")
    (output / "metrics.json").write_text(json.dumps(overall, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "dataset_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "feature_names.json").write_text(json.dumps(FEATURE_NAMES, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(output / "fold_history.csv", list(outer_rows[0]), outer_rows)
    write_csv(output / "candidate_history.csv", list(candidate_rows[0]), candidate_rows)
    write_csv(output / "final_candidate_history.csv", list(full_candidate_rows[0]), full_candidate_rows)
    write_csv(output / "splits.csv", list(split_rows[0]), split_rows)
    matrix = confusion_matrix(y, oof_prediction, labels=CLASSES)
    with (output / "confusion_matrix.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle); writer.writerow(["actual/predicted", *CLASSES])
        for label, row in zip(CLASSES, matrix): writer.writerow([label, *row.tolist()])
    history = {
        "seed": seed,
        "steps": [
            "Loaded all 20 official MATLAB ground-truth files.",
            "Removed fallen frames from the four-class benchmark because only participant/office 1 contains them.",
            "Computed detector-box geometry features without using pixels or handwritten decision rules.",
            "Selected among three classifiers inside each outer development split.",
            "Evaluated on one entirely unseen participant and office at a time.",
            f"Selected {all_selected} as the best research candidate by four-group cross-validation.",
            f"Applied the quality gate: {overall['quality_gate']['status']}. No deployable artifact is written when the gate fails.",
        ],
        "outer_folds": outer_rows,
        "best_research_candidate": all_selected,
        "candidate_training_frame_cap": int(final_train_idx.size),
        "quality_gate": overall["quality_gate"],
    }
    (output / "training_history.json").write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    card = f"""# Edinburgh Office Context Model Card

## Purpose

Auxiliary HealthVerse context head for classifying `empty`, `standing_walking`, `sitting`, and `talking` from up to four person bounding boxes produced by a separate detector. It does not replace the MediaPipe fine-posture model.

## Real data and evaluation

- Dataset: University of Edinburgh Office Monitoring Video Dataset, 20 days, four participants in four offices.
- Input used here: all official per-frame ground-truth bounding boxes and activity labels; no generated or simulated samples.
- License: CC BY-NC-SA. Raw dataset files are excluded from Git and are not redistributed.
- Evaluation: nested leave-one-participant-and-office-out. Candidate selection occurs only within the three development groups of each outer fold.
- Evaluated frames: {len(samples):,}.
- Final-candidate fitting frames: {len(final_train_idx):,} real frames, capped per participant/class to reduce adjacent-frame redundancy. The fitted candidate is discarded when the gate fails.
- Accuracy: {overall['accuracy']:.6f}.
- Macro-F1: {overall['macro_f1']:.6f}.
- Quality gate: **{overall['quality_gate']['status']}**.
- Gate thresholds: Accuracy ≥ 0.80, Macro-F1 ≥ 0.80, every-class recall ≥ 0.50.
- Failures: {'; '.join(overall['quality_gate']['failures']) if failures else 'none'}.

## Important limitation

The dataset contains {audit['excluded_fallen_frames']} fallen frames, all from {', '.join(audit['excluded_fallen_subjects'])}. They are excluded from the four-class score because a subject-disjoint fall benchmark is impossible with one positive participant. The model must not be represented as a validated fall detector. Bounding boxes came from ground truth during training/evaluation; production accuracy also depends on the upstream detector.

The official page describes up to three people, while the downloaded annotations contain {audit['annotation_row_counts'].get('4', 0)} frames with four annotation rows. The feature contract therefore accepts four boxes rather than silently discarding these records.

## Deployment decision

This run is **not deployable and is not integrated into HealthVerse** when the quality gate is rejected. The best research candidate was `{all_selected}`, but no model artifact is emitted after a failed gate. Improving unseen-office generalization requires image/pose evidence or scene calibration, not merely more tuning of bounding-box geometry.
"""
    (output / "model_card.md").write_text(card, encoding="utf-8")
    print(json.dumps({"metrics": overall, "audit": {k: v for k, v in audit.items() if k != "day_counts"}, "best_research_candidate": all_selected}, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gt-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    train(args.gt_dir, args.output, args.seed)


if __name__ == "__main__":
    main()
