"""Train a subject-disjoint BEHAVE interaction classifier from official fits.

The script deliberately does not use SMPL beta/body-shape parameters. It uses
pose rotations and human/object rigid transforms only. Sequence names provide
the source-derived action labels; no medical or ergonomic outcome is inferred.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, recall_score


SUBJECT_PATTERN = re.compile(r"_Sub(\d+)_")


@dataclass(frozen=True)
class SequenceBatch:
    sequence: str
    subject: str
    label: str
    features: np.ndarray
    frame_times: list[str]


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def classify_sequence(name: str, classes: dict[str, list[str]], excluded: set[str]) -> str | None:
    suffix = name.split("_", 2)[-1]
    if suffix in excluded:
        return None
    matches = [label for label, suffixes in classes.items() if suffix in suffixes]
    if len(matches) > 1:
        raise ValueError(f"sequence {name!r} matches more than one class: {matches}")
    return matches[0] if matches else None


def _common_frame_indices(human_times: np.ndarray, object_times: np.ndarray) -> tuple[np.ndarray, np.ndarray, list[str]]:
    human_index = {str(value): index for index, value in enumerate(human_times.tolist())}
    object_index = {str(value): index for index, value in enumerate(object_times.tolist())}
    common = sorted(set(human_index) & set(object_index), key=lambda value: float(value.removeprefix("t")))
    if not common:
        raise ValueError("human and object fits have no common frame timestamps")
    return (
        np.asarray([human_index[value] for value in common], dtype=int),
        np.asarray([object_index[value] for value in common], dtype=int),
        common,
    )


def _sample_indices(count: int, maximum: int, trim_fraction: float) -> np.ndarray:
    if count < 3:
        return np.arange(count, dtype=int)
    lower = int(np.floor(count * trim_fraction))
    upper = int(np.ceil(count * (1.0 - trim_fraction))) - 1
    if upper <= lower:
        lower, upper = 0, count - 1
    sample_count = min(maximum, upper - lower + 1)
    return np.unique(np.linspace(lower, upper, sample_count, dtype=int))


def load_sequence(path: Path, label: str, samples_per_sequence: int, trim_fraction: float) -> SequenceBatch:
    subject_match = SUBJECT_PATTERN.search(path.name)
    if not subject_match:
        raise ValueError(f"cannot parse subject from {path.name!r}")
    subject = f"Sub{subject_match.group(1)}"
    with np.load(path / "smpl_fit_all.npz") as human, np.load(path / "object_fit_all.npz") as obj:
        human_idx, object_idx, common_times = _common_frame_indices(human["frame_times"], obj["frame_times"])
        pose = np.asarray(human["poses"][human_idx], dtype=np.float32)
        human_trans = np.asarray(human["trans"][human_idx], dtype=np.float32)
        object_angles = np.asarray(obj["angles"][object_idx], dtype=np.float32)
        object_trans = np.asarray(obj["trans"][object_idx], dtype=np.float32)

    if pose.ndim != 2 or pose.shape[1] != 156:
        raise ValueError(f"unexpected pose shape in {path.name}: {pose.shape}")
    relative_trans = object_trans - human_trans
    pose_delta = np.vstack([np.zeros((1, pose.shape[1]), dtype=np.float32), np.diff(pose, axis=0)])
    human_delta = np.vstack([np.zeros((1, 3), dtype=np.float32), np.diff(human_trans, axis=0)])
    object_delta = np.vstack([np.zeros((1, 3), dtype=np.float32), np.diff(object_trans, axis=0)])
    relative_delta = np.vstack([np.zeros((1, 3), dtype=np.float32), np.diff(relative_trans, axis=0)])
    features = np.hstack([
        pose,
        human_trans,
        relative_trans,
        object_angles,
        pose_delta,
        human_delta,
        object_delta,
        relative_delta,
    ]).astype(np.float32, copy=False)
    if not np.isfinite(features).all():
        raise ValueError(f"non-finite feature in {path.name}")
    selected = _sample_indices(len(features), samples_per_sequence, trim_fraction)
    return SequenceBatch(
        sequence=path.name,
        subject=subject,
        label=label,
        features=features[selected],
        frame_times=[common_times[index] for index in selected],
    )


def load_dataset(config: dict, repo_root: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[str]]:
    root = repo_root / config["local_params"]
    if not root.is_dir():
        raise FileNotFoundError(f"BEHAVE parameters not found: {root}")
    batches: list[SequenceBatch] = []
    excluded = set(config["excluded_ambiguous_suffixes"])
    for sequence_path in sorted(path for path in root.iterdir() if path.is_dir()):
        label = classify_sequence(sequence_path.name, config["classes"], excluded)
        if label is None:
            continue
        batches.append(load_sequence(
            sequence_path,
            label,
            int(config["samples_per_sequence"]),
            float(config["temporal_trim_fraction"]),
        ))
    if not batches:
        raise ValueError("no matching BEHAVE sequences were loaded")
    x = np.vstack([batch.features for batch in batches])
    y = np.concatenate([np.repeat(batch.label, len(batch.features)) for batch in batches])
    subjects = np.concatenate([np.repeat(batch.subject, len(batch.features)) for batch in batches])
    sequences = np.concatenate([np.repeat(batch.sequence, len(batch.features)) for batch in batches])
    frame_times = [time for batch in batches for time in batch.frame_times]
    return x, y, subjects, sequences, frame_times


def estimator(config: dict, seed_offset: int = 0) -> ExtraTreesClassifier:
    settings = config["estimator"]
    return ExtraTreesClassifier(
        n_estimators=int(settings["n_estimators"]),
        min_samples_leaf=int(settings["min_samples_leaf"]),
        max_features=settings["max_features"],
        class_weight=settings["class_weight"],
        random_state=int(config["random_seed"]) + seed_offset,
        n_jobs=-1,
    )


def metric_record(y_true: np.ndarray, y_pred: np.ndarray, labels: list[str]) -> dict:
    recalls = recall_score(y_true, y_pred, labels=labels, average=None, zero_division=0)
    support = {label: int(np.sum(y_true == label)) for label in labels}
    supported_labels = [label for label in labels if support[label] > 0]
    macro_all = float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0))
    macro_supported = float(f1_score(
        y_true, y_pred, labels=supported_labels, average="macro", zero_division=0
    ))
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": macro_all,
        "macro_f1_supported_classes": macro_supported,
        "supported_labels": supported_labels,
        "per_class_recall": {label: float(value) for label, value in zip(labels, recalls)},
        "class_support": support,
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("machine-learning/datasets/behave-relation.json"))
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    config_path = args.config if args.config.is_absolute() else repo_root / args.config
    config = load_config(config_path)
    output = repo_root / config["output_dir"]
    output.mkdir(parents=True, exist_ok=True)

    x, y, subjects, sequences, frame_times = load_dataset(config, repo_root)
    labels = list(config["classes"])
    unique_subjects = sorted(np.unique(subjects).tolist())
    fold_history: list[dict] = []
    all_true: list[str] = []
    all_pred: list[str] = []
    split_rows: list[dict] = []
    for fold_index, holdout in enumerate(unique_subjects):
        test_mask = subjects == holdout
        train_mask = ~test_mask
        model = estimator(config, fold_index)
        model.fit(x[train_mask], y[train_mask])
        predicted = model.predict(x[test_mask])
        record = metric_record(y[test_mask], predicted, labels)
        record.update({
            "holdout_subject": holdout,
            "train_samples": int(train_mask.sum()),
            "test_samples": int(test_mask.sum()),
            "train_sequences": int(np.unique(sequences[train_mask]).size),
            "test_sequences": int(np.unique(sequences[test_mask]).size),
        })
        fold_history.append(record)
        all_true.extend(y[test_mask].tolist())
        all_pred.extend(predicted.tolist())
        for index in np.flatnonzero(test_mask):
            split_rows.append({
                "sequence": sequences[index],
                "subject": subjects[index],
                "frame_time": frame_times[index],
                "true_label": y[index],
                "predicted_label": predicted[np.sum(test_mask[:index])],
                "fold": holdout,
            })

    all_true_array = np.asarray(all_true)
    all_pred_array = np.asarray(all_pred)
    aggregate = metric_record(all_true_array, all_pred_array, labels)
    matrix = confusion_matrix(all_true_array, all_pred_array, labels=labels)
    gate = config["quality_gate"]
    gate_failures: list[str] = []
    if aggregate["macro_f1"] < float(gate["minimum_aggregate_macro_f1"]):
        gate_failures.append(
            f"aggregate macro-F1 {aggregate['macro_f1']:.6f} is below "
            f"{float(gate['minimum_aggregate_macro_f1']):.6f}"
        )
    for label, value in aggregate["per_class_recall"].items():
        if value < float(gate["minimum_aggregate_class_recall"]):
            gate_failures.append(
                f"aggregate recall for {label} {value:.6f} is below "
                f"{float(gate['minimum_aggregate_class_recall']):.6f}"
            )
    sequence_labels = {sequence: y[np.flatnonzero(sequences == sequence)[0]] for sequence in np.unique(sequences)}
    metrics = {
        "dataset": {
            "id": config["dataset_id"],
            "source_url": config["source_url"],
            "license": config["license"],
            "raw_data_redistributed": False,
        },
        "protocol": config["evaluation"],
        "feature_contract": {
            "dimensions": int(x.shape[1]),
            "uses_smpl_betas": False,
            "components": [
                "smpl_pose_axis_angles_156",
                "human_translation_3",
                "object_minus_human_translation_3",
                "object_axis_angles_3",
                "smpl_pose_frame_delta_156",
                "human_translation_frame_delta_3",
                "object_translation_frame_delta_3",
                "relative_translation_frame_delta_3"
            ],
        },
        "data_summary": {
            "subjects": unique_subjects,
            "subject_count": len(unique_subjects),
            "sequence_count": int(np.unique(sequences).size),
            "sample_count": int(len(y)),
            "samples_per_class": dict(Counter(y.tolist())),
            "sequences_per_class": dict(Counter(sequence_labels.values())),
            "samples_per_subject": dict(Counter(subjects.tolist())),
        },
        "aggregate_loso": aggregate,
        "quality_gate": {
            "thresholds": gate,
            "status": "passed" if not gate_failures else "failed",
            "failures": gate_failures,
        },
        "fold_metric_mean": {
            "accuracy": float(np.mean([fold["accuracy"] for fold in fold_history])),
            "macro_f1_supported_classes": float(np.mean([
                fold["macro_f1_supported_classes"] for fold in fold_history
            ])),
        },
        "fold_metric_std": {
            "accuracy": float(np.std([fold["accuracy"] for fold in fold_history], ddof=1)),
            "macro_f1_supported_classes": float(np.std([
                fold["macro_f1_supported_classes"] for fold in fold_history
            ], ddof=1)),
        },
        "limitations": [
            "Labels are source-derived interaction categories from sequence names, not ergonomic risk or medical outcome labels.",
            "Frames are subsampled evenly per sequence; LOSO prevents identity leakage, but adjacent moments from one sequence remain correlated within one fold.",
            "Sub08 has no table_lean sequence, so that fold has zero support for table_lean; aggregate LOSO includes all classes.",
            "The input requires fitted SMPL/object transforms and is not yet a raw-RGB browser model.",
        ],
    }

    final_model = estimator(config, 100)
    final_model.fit(x, y)
    artifact = {
        "model": final_model,
        "labels": labels,
        "feature_contract": metrics["feature_contract"],
        "dataset_license": config["license"],
        "redistribution_notice": "Keep local unless the BEHAVE dataset owner confirms derived-weight redistribution.",
    }
    model_path = output / "model.joblib"
    joblib.dump(artifact, model_path)
    metrics["local_model_artifact"] = {
        "path": "model.joblib",
        "sha256": sha256(model_path),
        "tracked_by_git": False,
    }

    (output / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    (output / "fold_history.json").write_text(json.dumps(fold_history, indent=2, ensure_ascii=False), encoding="utf-8")
    with (output / "confusion_matrix.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["true\\pred", *labels])
        for label, row in zip(labels, matrix):
            writer.writerow([label, *row.tolist()])
    with (output / "splits.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["sequence", "subject", "frame_time", "true_label", "predicted_label", "fold"])
        writer.writeheader()
        writer.writerows(split_rows)

    model_card = f"""# BEHAVE relation model card

## Intended task

Auxiliary classification of three observed human-object interaction states from fitted body/object transforms: `seated_contact`, `table_lean`, and `monitor_interaction`. This is not a medical model and does not assign ergonomic risk.

## Real data and split

- Source: [{config['paper']}]({config['source_url']})
- Participants used: {len(unique_subjects)} ({', '.join(unique_subjects)})
- Sequences: {metrics['data_summary']['sequence_count']}
- Subsampled frames: {metrics['data_summary']['sample_count']} ({config['samples_per_sequence']} maximum per sequence)
- Evaluation: leave one complete `SubXX` participant out. Shape/identity parameters (`betas`) are excluded.

## Held-out-participant result

- Aggregate accuracy: **{aggregate['accuracy']:.4f}**
- Aggregate macro-F1: **{aggregate['macro_f1']:.4f}**
- Per-class recall: {json.dumps(aggregate['per_class_recall'], ensure_ascii=False)}
- Quality gate: **{metrics['quality_gate']['status'].upper()}** (macro-F1 ≥ {gate['minimum_aggregate_macro_f1']}; every aggregate class recall ≥ {gate['minimum_aggregate_class_recall']})
- Fold mean accuracy: {metrics['fold_metric_mean']['accuracy']:.4f} ± {metrics['fold_metric_std']['accuracy']:.4f}
- Fold mean macro-F1 over classes present in each test subject: **{metrics['fold_metric_mean']['macro_f1_supported_classes']:.4f} ± {metrics['fold_metric_std']['macro_f1_supported_classes']:.4f}**

## License and artifact boundary

BEHAVE is licensed for non-commercial scientific research. Source files are not redistributed. The fitted `model.joblib` is generated locally and ignored by Git pending explicit clarification that derived weights may be redistributed. Its SHA-256 is recorded in `metrics.json`.

## Limitations

{chr(10).join('- ' + item for item in metrics['limitations'])}
"""
    (output / "model_card.md").write_text(model_card, encoding="utf-8")
    print(json.dumps(metrics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
