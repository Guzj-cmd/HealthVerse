from __future__ import annotations

import argparse
import csv
import json
import math
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

import joblib
import numpy as np
from PIL import Image
from sklearn.base import clone
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, recall_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC


SOURCE_URL = "https://groups.inf.ed.ac.uk/vision/DATASETS/HUMOLS/"
DATASET_URL = "https://datashare.ed.ac.uk/handle/10283/8851"
LABELS = ["lying", "sitting", "standing"]


@dataclass(frozen=True)
class Record:
    video_id: int
    scenario: str
    gender: str
    pose: str
    view: str


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_table = False
        self.in_cell = False
        self.current_cell: list[str] = []
        self.current_row: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self.in_table = True
        elif self.in_table and tag == "tr":
            self.current_row = []
        elif self.in_table and tag in {"td", "th"}:
            self.in_cell = True
            self.current_cell = []

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.current_cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.in_table and tag in {"td", "th"}:
            self.current_row.append(" ".join("".join(self.current_cell).split()))
            self.in_cell = False
        elif self.in_table and tag == "tr":
            if self.current_row:
                self.rows.append(self.current_row)
        elif tag == "table":
            self.in_table = False


def load_official_metadata(url: str) -> list[Record]:
    request = urllib.request.Request(url, headers={"User-Agent": "HealthVerse research adapter/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        parser = _TableParser()
        parser.feed(response.read().decode("utf-8", errors="replace"))
    records: list[Record] = []
    for row in parser.rows:
        if len(row) < 5 or not row[0].isdigit():
            continue
        record = Record(int(row[0]), row[1], row[2], row[3].lower(), row[4].lower())
        if record.pose not in LABELS:
            raise ValueError(f"unexpected HuMoLs pose label: {record.pose!r}")
        records.append(record)
    if len(records) != 101 or len({record.video_id for record in records}) != 101:
        raise ValueError(f"expected 101 unique HuMoLs records, found {len(records)}")
    return sorted(records, key=lambda record: record.video_id)


def _resample(values: np.ndarray, count: int) -> np.ndarray:
    if len(values) == 1:
        return np.repeat(values, count)
    source = np.linspace(0.0, 1.0, len(values))
    target = np.linspace(0.0, 1.0, count)
    return np.interp(target, source, values)


def silhouette_features(path: Path) -> np.ndarray:
    mask = np.asarray(Image.open(path).convert("L")) >= 128
    points = np.argwhere(mask)
    if not len(points):
        raise ValueError(f"empty silhouette: {path}")
    height, width = mask.shape
    y0, x0 = points.min(axis=0)
    y1, x1 = points.max(axis=0) + 1
    crop = mask[y0:y1, x0:x1]
    crop_height, crop_width = crop.shape

    normalized = np.asarray(
        Image.fromarray((crop * 255).astype(np.uint8)).resize((16, 16), Image.Resampling.NEAREST),
        dtype=np.float64,
    ).reshape(-1) / 255.0
    horizontal = _resample(crop.mean(axis=1), 32)
    vertical = _resample(crop.mean(axis=0), 32)

    y = points[:, 0] / max(height - 1, 1)
    x = points[:, 1] / max(width - 1, 1)
    covariance = np.cov(np.stack([x, y]), bias=True)
    eigenvalues = np.sort(np.linalg.eigvalsh(covariance))[::-1]
    perimeter = (
        np.logical_xor(mask[:, 1:], mask[:, :-1]).sum()
        + np.logical_xor(mask[1:, :], mask[:-1, :]).sum()
    )
    grid: list[float] = []
    for gy in range(4):
        for gx in range(4):
            ys = slice(round(gy * height / 4), round((gy + 1) * height / 4))
            xs = slice(round(gx * width / 4), round((gx + 1) * width / 4))
            grid.append(float(mask[ys, xs].mean()))
    global_features = np.asarray([
        mask.mean(), crop_width / width, crop_height / height,
        crop_width / max(crop_height, 1), (crop_width * crop_height) / (width * height),
        x.mean(), y.mean(), x.std(), y.std(),
        eigenvalues[0], eigenvalues[1],
        eigenvalues[0] / max(eigenvalues[1], 1e-9),
        perimeter / max(mask.sum(), 1),
    ], dtype=np.float64)
    result = np.concatenate([global_features, np.asarray(grid), horizontal, vertical, normalized])
    if not np.isfinite(result).all():
        raise ValueError(f"non-finite silhouette features: {path}")
    return result


def evaluate(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, object]:
    recalls = recall_score(y_true, y_pred, labels=LABELS, average=None, zero_division=0)
    return {
        "sample_count": int(len(y_true)),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, labels=LABELS, average="macro", zero_division=0)),
        "per_class_recall": {label: float(value) for label, value in zip(LABELS, recalls)},
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=LABELS).tolist(),
    }


def candidates(seed: int) -> dict[str, object]:
    return {
        "balanced_logistic": make_pipeline(
            StandardScaler(),
            LogisticRegression(C=1.0, class_weight="balanced", max_iter=3000, random_state=seed),
        ),
        "balanced_rbf_svc": make_pipeline(
            StandardScaler(),
            SVC(C=3.0, gamma="scale", class_weight="balanced", random_state=seed),
        ),
        "extra_trees": ExtraTreesClassifier(
            n_estimators=500, max_features="sqrt", min_samples_leaf=1,
            class_weight="balanced", random_state=seed, n_jobs=-1,
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=500, max_features="sqrt", min_samples_leaf=1,
            class_weight="balanced_subsample", random_state=seed, n_jobs=-1,
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="HuMoLs silhouette scene/view robustness experiment")
    parser.add_argument("--masks", required=True, help="extracted official all_masks.zip directory")
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", type=int, default=20261125)
    parser.add_argument("--source-url", default=SOURCE_URL)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)

    records = load_official_metadata(args.source_url)
    masks_root = Path(args.masks)
    mask_by_id = {
        int(path.stem.rsplit("_", 1)[-1]): path
        for path in masks_root.rglob("person_mask_*.png")
    }
    missing = sorted({record.video_id for record in records} - set(mask_by_id))
    if missing:
        raise FileNotFoundError(f"missing official masks for video IDs: {missing}")

    X = np.stack([silhouette_features(mask_by_id[record.video_id]) for record in records])
    y = np.asarray([record.pose for record in records])
    outer = StratifiedKFold(n_splits=4, shuffle=True, random_state=args.seed)
    predictions = np.empty(len(records), dtype=object)
    split_rows: list[dict[str, object]] = []
    fold_rows: list[dict[str, object]] = []
    model_candidates = candidates(args.seed)

    for outer_fold, (development, test) in enumerate(outer.split(X, y), start=1):
        inner = StratifiedKFold(n_splits=3, shuffle=True, random_state=args.seed + outer_fold)
        candidate_scores: list[tuple[float, float, str]] = []
        for name, prototype in model_candidates.items():
            inner_prediction = np.empty(len(development), dtype=object)
            for inner_train, validation in inner.split(X[development], y[development]):
                model = clone(prototype)
                model.fit(X[development][inner_train], y[development][inner_train])
                inner_prediction[validation] = model.predict(X[development][validation])
            score = evaluate(y[development], inner_prediction)
            candidate_scores.append((float(score["macro_f1"]), float(score["accuracy"]), name))
        candidate_scores.sort(reverse=True)
        winner_name = candidate_scores[0][2]
        winner = clone(model_candidates[winner_name])
        winner.fit(X[development], y[development])
        predictions[test] = winner.predict(X[test])
        fold_result = evaluate(y[test], predictions[test])
        fold_rows.append({
            "fold": outer_fold,
            "winner": winner_name,
            "development_samples": int(len(development)),
            "test_samples": int(len(test)),
            "inner_candidates": [
                {"candidate": name, "macro_f1": macro_f1, "accuracy": accuracy}
                for macro_f1, accuracy, name in candidate_scores
            ],
            "test": fold_result,
        })
        test_set = set(test.tolist())
        for index, record in enumerate(records):
            split_rows.append({
                "outer_fold": outer_fold,
                "video_id": record.video_id,
                "partition": "test" if index in test_set else "development",
                "pose": record.pose,
                "scenario": record.scenario,
                "view": record.view,
            })

    pooled = evaluate(y, predictions.astype(str))
    quality_gate = {
        "minimum_macro_f1": 0.80,
        "minimum_per_class_recall": 0.50,
        "passed": bool(
            pooled["macro_f1"] >= 0.80
            and min(pooled["per_class_recall"].values()) >= 0.50
        ),
    }
    by_scenario: dict[str, dict[str, object]] = {}
    for scenario in sorted({record.scenario for record in records}):
        indices = np.asarray([index for index, record in enumerate(records) if record.scenario == scenario])
        by_scenario[scenario] = evaluate(y[indices], predictions[indices].astype(str))
    by_view: dict[str, dict[str, object]] = {}
    for view in sorted({record.view for record in records}):
        indices = np.asarray([index for index, record in enumerate(records) if record.view == view])
        by_view[view] = evaluate(y[indices], predictions[indices].astype(str))

    # The deployable artifact is fitted on all 101 videos. The nested-CV pooled
    # result above, not this final fit, is the reported estimate.
    winner_counts: defaultdict[str, int] = defaultdict(int)
    for row in fold_rows:
        winner_counts[str(row["winner"])] += 1
    final_winner_name = max(winner_counts, key=lambda name: (winner_counts[name], name))
    final_model = clone(model_candidates[final_winner_name])
    final_model.fit(X, y)
    joblib.dump({
        "model": final_model,
        "labels": LABELS,
        "feature_count": int(X.shape[1]),
        "input": "one binary person silhouette mask",
        "dataset": "HuMoLs",
    }, output / "model.joblib")

    report = {
        "experiment_status": "completed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset": {
            "name": "Human MotionLess Dataset (HuMoLs)",
            "source": DATASET_URL,
            "metadata_source": args.source_url,
            "citation": "Chen, Fisher and Raza (2024), doi:10.7488/ds/7796; cite OPPH (ACVR/ECCV Workshop 2024)",
            "use_terms": "Official description states the dataset can be used freely with citation.",
            "videos": len(records),
            "class_support": {label: int(np.sum(y == label)) for label in LABELS},
            "scenario_support": {scenario: sum(record.scenario == scenario for record in records) for scenario in sorted({record.scenario for record in records})},
            "view_support": {view: sum(record.view == view for record in records) for view in sorted({record.view for record in records})},
        },
        "protocol": {
            "outer_evaluation": "4-fold stratified cross-validation; each official video contributes one mask and appears in one test fold",
            "model_selection": "3-fold stratified CV within each outer development partition",
            "raw_video_used": False,
            "subject_disjoint": False,
            "reason": "The official release has no participant identifier; the repository description calls it a single-subject dataset even though metadata contains M/F entries.",
        },
        "pooled_outer_cv": pooled,
        "quality_gate": quality_gate,
        "by_scenario": by_scenario,
        "by_view": by_view,
        "folds": fold_rows,
        "artifact_model": final_winner_name,
        "deployment_status": "accepted" if quality_gate["passed"] else "rejected",
        "limitations": [
            "This is a silhouette scene/view robustness experiment, not participant-generalization evidence.",
            "There are only four standing videos; standing recall has very high uncertainty.",
            "A supplied foreground mask is assumed. This model does not segment a person from RGB input.",
            "Motionless pose classes do not provide fine-grained ergonomic sitting labels or health diagnoses."
        ],
    }
    (output / "metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "fold_history.json").write_text(json.dumps(fold_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    with (output / "splits.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(split_rows[0]))
        writer.writeheader()
        writer.writerows(split_rows)
    with (output / "confusion_matrix.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["actual/predicted", *LABELS])
        for label, row in zip(LABELS, pooled["confusion_matrix"]):
            writer.writerow([label, *row])
    model_card = f"""# HuMoLs silhouette robustness model

## Intended use

Auxiliary classification of a supplied binary person silhouette as `lying`, `sitting`, or `standing`. This experiment tests pose-shape robustness across the real HuMoLs scenarios and camera views. It is not the HealthVerse fine-grained sitting model and is not a medical diagnosis.

## Data and protocol

- 101 official HuMoLs videos, represented by the one official person mask released for each video.
- Nested evaluation: four stratified outer folds and three stratified inner folds for model selection.
- Raw RGB videos were not used or redistributed.
- Pooled outer-CV accuracy: **{pooled['accuracy']:.4f}**
- Pooled outer-CV macro-F1: **{pooled['macro_f1']:.4f}**
- Per-class recall: {json.dumps(pooled['per_class_recall'], ensure_ascii=False)}

## Critical limitations

The release has no participant identifier, so no participant-disjoint claim is possible. The official description calls the release single-subject, while the table contains both M/F metadata. There are only four standing videos. Results are therefore descriptive scene/view robustness evidence only. Inference also assumes a foreground silhouette supplied by an upstream segmentation model.

## Quality gate

Status: **{'PASSED' if quality_gate['passed'] else 'REJECTED'}**. The acceptance gate requires macro-F1 >= 0.80 and every class recall >= 0.50. A rejected artifact is retained only to document the real experiment and must not be integrated as a production model.

Source: <{DATASET_URL}>. The official description permits free use with citation and asks users to cite OPPH (ACVR/ECCV Workshop 2024).
"""
    (output / "model_card.md").write_text(model_card, encoding="utf-8")
    print(json.dumps({"output": str(output), "pooled_outer_cv": pooled, "winner": final_winner_name}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
