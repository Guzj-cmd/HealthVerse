from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np


@dataclass(frozen=True)
class PoseSample:
    sample_id: str
    subject_id: str
    label: str
    source: str
    landmarks: np.ndarray  # (33, 4): x, y, z, visibility
    dataset_id: str = "unknown"


def _landmarks_from_json(value: object) -> np.ndarray:
    if not isinstance(value, list) or len(value) != 33:
        raise ValueError("landmarks must contain exactly 33 MediaPipe points")
    rows = []
    for item in value:
        if isinstance(item, dict):
            rows.append([item.get("x"), item.get("y"), item.get("z", 0.0), item.get("visibility", 1.0)])
        elif isinstance(item, list) and len(item) in (3, 4):
            rows.append([*item, 1.0] if len(item) == 3 else item)
        else:
            raise ValueError("each landmark must be an object or a 3/4-value list")
    array = np.asarray(rows, dtype=np.float64)
    if array.shape != (33, 4) or not np.isfinite(array).all():
        raise ValueError("landmarks must be finite numeric values with shape (33, 4)")
    return array


def _landmarks_from_csv(row: dict[str, str]) -> np.ndarray:
    points = []
    for index in range(33):
        try:
            points.append([
                float(row[f"x{index}"]), float(row[f"y{index}"]),
                float(row.get(f"z{index}", 0.0)), float(row.get(f"v{index}", 1.0)),
            ])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid landmark columns at index {index}") from exc
    array = np.asarray(points, dtype=np.float64)
    if not np.isfinite(array).all():
        raise ValueError("landmarks contain non-finite values")
    return array


def load_samples(path: str | Path) -> list[PoseSample]:
    source_path = Path(path)
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    samples: list[PoseSample] = []
    if source_path.suffix.lower() == ".jsonl":
        with source_path.open("r", encoding="utf-8-sig") as handle:
            rows: Iterable[dict[str, object]] = (
                json.loads(line) for line in handle if line.strip()
            )
            for offset, row in enumerate(rows, start=1):
                samples.append(PoseSample(
                    str(row.get("sample_id", offset)), str(row["subject_id"]),
                    str(row["label"]), str(row.get("source", source_path.name)),
                    _landmarks_from_json(row["landmarks"]),
                    str(row.get("dataset_id", source_path.stem)),
                ))
    elif source_path.suffix.lower() == ".csv":
        with source_path.open("r", encoding="utf-8-sig", newline="") as handle:
            for offset, row in enumerate(csv.DictReader(handle), start=1):
                samples.append(PoseSample(
                    row.get("sample_id") or str(offset), row["subject_id"], row["label"],
                    row.get("source") or source_path.name, _landmarks_from_csv(row),
                    row.get("dataset_id") or source_path.stem,
                ))
    else:
        raise ValueError("supported dataset formats are .csv and .jsonl")
    if not samples:
        raise ValueError("dataset is empty")
    return samples


def write_jsonl_sample(handle, sample: PoseSample) -> None:
    row = {
        "sample_id": sample.sample_id,
        "subject_id": sample.subject_id,
        "label": sample.label,
        "source": sample.source,
        "dataset_id": sample.dataset_id,
        "landmarks": [
            {"x": float(p[0]), "y": float(p[1]), "z": float(p[2]), "visibility": float(p[3])}
            for p in sample.landmarks
        ],
    }
    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
