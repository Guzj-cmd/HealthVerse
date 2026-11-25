from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable

from .io import PoseSample, load_samples


DATASET_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$")


@dataclass(frozen=True)
class DatasetSpec:
    """Mapping contract for one external dataset.

    `label_map` is intentionally explicit. Labels absent from the map are
    rejected instead of being guessed from similar names.
    """

    dataset_id: str
    label_map: dict[str, str]
    landmark_schema: str = "mediapipe33"
    license: str | None = None
    citation: str | None = None

    def __post_init__(self) -> None:
        if not DATASET_ID_PATTERN.fullmatch(self.dataset_id):
            raise ValueError("dataset_id must be a stable lowercase identifier")
        if self.landmark_schema != "mediapipe33":
            raise ValueError("only mediapipe33 landmarks are currently supported")
        if not self.label_map:
            raise ValueError("label_map cannot be empty")


def load_dataset_spec(path: str | Path) -> DatasetSpec:
    with Path(path).open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    return DatasetSpec(
        dataset_id=str(value["dataset_id"]),
        label_map={str(key): str(mapped) for key, mapped in value["label_map"].items()},
        landmark_schema=str(value.get("landmark_schema", "mediapipe33")),
        license=str(value["license"]) if value.get("license") else None,
        citation=str(value["citation"]) if value.get("citation") else None,
    )


def load_mapped_samples(path: str | Path, spec: DatasetSpec) -> list[PoseSample]:
    """Load, map labels, and namespace identities for safe dataset merging."""

    mapped: list[PoseSample] = []
    for sample in load_samples(path):
        if sample.label not in spec.label_map:
            raise ValueError(
                f"dataset {spec.dataset_id!r} has unmapped label {sample.label!r}; "
                "add an explicit label_map entry or exclude the sample"
            )
        mapped.append(replace(
            sample,
            sample_id=f"{spec.dataset_id}:{sample.sample_id}",
            subject_id=f"{spec.dataset_id}:{sample.subject_id}",
            label=spec.label_map[sample.label],
            dataset_id=spec.dataset_id,
        ))
    return mapped


def merge_mapped_datasets(items: Iterable[tuple[str | Path, DatasetSpec]]) -> list[PoseSample]:
    merged: list[PoseSample] = []
    dataset_ids: set[str] = set()
    sample_ids: set[str] = set()
    for path, spec in items:
        if spec.dataset_id in dataset_ids:
            raise ValueError(f"duplicate dataset_id: {spec.dataset_id}")
        dataset_ids.add(spec.dataset_id)
        for sample in load_mapped_samples(path, spec):
            if sample.sample_id in sample_ids:
                raise ValueError(f"duplicate sample_id after namespacing: {sample.sample_id}")
            sample_ids.add(sample.sample_id)
            merged.append(sample)
    if not merged:
        raise ValueError("no mapped samples were loaded")
    return merged
