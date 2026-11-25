"""Label real MultiPosture observations with the configured local Codex AI teacher."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import tempfile
import tomllib
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


def sha256_json(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def angle_from_vertical(vector: np.ndarray) -> float:
    vertical = abs(float(vector[1])); horizontal = float(np.linalg.norm(vector[[0, 2]]))
    return math.degrees(math.atan2(horizontal, max(vertical, 1e-9)))


def derive_context(row: pd.Series, row_index: int) -> dict:
    left_shoulder = row[["left_shoulder_x", "left_shoulder_y", "left_shoulder_z"]].to_numpy(float)
    right_shoulder = row[["right_shoulder_x", "right_shoulder_y", "right_shoulder_z"]].to_numpy(float)
    left_hip = row[["left_hip_x", "left_hip_y", "left_hip_z"]].to_numpy(float)
    right_hip = row[["right_hip_x", "right_hip_y", "right_hip_z"]].to_numpy(float)
    nose = row[["nose_x", "nose_y", "nose_z"]].to_numpy(float)
    shoulder_mid = (left_shoulder + right_shoulder) / 2
    hip_mid = (left_hip + right_hip) / 2
    context = {
        "sample_id": f"mp-{int(row.subject):02d}-{row_index:04d}",
        "subject_id": str(int(row.subject)),
        "source_row_index": int(row_index),
        "source": "MultiPosture_v1_Zenodo_14230872",
        "observed_upper_posture": row.upperbody_label,
        "observed_lower_posture": row.lowerbody_label,
        "derived_trunk_angle_from_vertical_deg": round(angle_from_vertical(shoulder_mid - hip_mid), 3),
        "derived_neck_angle_from_vertical_deg": round(angle_from_vertical(nose - shoulder_mid), 3),
        "derived_shoulder_tilt_deg": round(abs(math.degrees(math.atan2(float(left_shoulder[1] - right_shoulder[1]), max(abs(float(left_shoulder[0] - right_shoulder[0])), 1e-9)))), 3),
        "environment_fields": "unavailable",
        "duration_min": None,
    }
    context["context_checksum"] = sha256_json(context)
    return context


def select_real_contexts(data: pd.DataFrame, per_stratum: int) -> list[dict]:
    feature_columns = [column for column in data.columns if column not in {"subject", "upperbody_label", "lowerbody_label"}]
    selected = []
    for (_, _), group in data.groupby(["subject", "upperbody_label"], sort=True):
        matrix = group[feature_columns].to_numpy(float)
        center = np.median(matrix, axis=0)
        order = np.argsort(np.linalg.norm(matrix - center, axis=1))[:per_stratum]
        for position in order:
            index = int(group.index[position]); selected.append(derive_context(data.loc[index], index))
    return selected


def local_teacher_model() -> str:
    config_path = Path.home() / ".codex" / "config.toml"
    if not config_path.exists(): return "local-codex-default"
    with config_path.open("rb") as handle: return str(tomllib.load(handle).get("model", "local-codex-default"))


def call_teacher(prompt: str, schema: Path, cwd: Path, timeout: int) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as handle:
        output_path = Path(handle.name)
    command = [
        "codex", "exec", "-", "--ephemeral", "--skip-git-repo-check", "--ignore-rules",
        "--sandbox", "read-only", "--output-schema", str(schema.resolve()),
        "--output-last-message", str(output_path), "--cd", str(cwd.resolve()), "--color", "never",
    ]
    try:
        completed = subprocess.run(command, input=prompt, text=True, encoding="utf-8", capture_output=True, timeout=timeout, check=False)
        if completed.returncode != 0:
            raise RuntimeError(f"codex teacher failed ({completed.returncode}): {completed.stderr[-1200:]}")
        return json.loads(output_path.read_text(encoding="utf-8"))
    finally:
        output_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--output", default="artifacts/teacher")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--batch-size", type=int, default=12)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    base = Path(__file__).resolve().parent; output = Path(args.output); output.mkdir(parents=True, exist_ok=True)
    config = json.loads(Path(args.config).read_text(encoding="utf-8")); settings = config["teacher_distillation"]
    prompt_template = (base / "teacher_prompt.md").read_text(encoding="utf-8")
    prompt_checksum = hashlib.sha256(prompt_template.encode("utf-8")).hexdigest()
    data = pd.read_csv(args.data)
    contexts = select_real_contexts(data, int(settings["samples_per_subject_posture"]))
    (output / "selected_contexts.json").write_text(json.dumps(contexts, ensure_ascii=False, indent=2), encoding="utf-8")
    state = {"state": "awaiting_teacher", "real_contexts": len(contexts), "passes_requested": settings["passes"], "teacher_model": local_teacher_model(), "prompt_version": settings["prompt_version"], "prompt_checksum": prompt_checksum}
    (output / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.prepare_only:
        print(json.dumps(state, ensure_ascii=False)); return 0

    annotations: dict[str, list[dict]] = {context["sample_id"]: [] for context in contexts}
    try:
        for pass_index in range(int(settings["passes"])):
            for start in range(0, len(contexts), args.batch_size):
                batch = contexts[start:start + args.batch_size]
                request = prompt_template + "\n\ncontexts = " + json.dumps(batch, ensure_ascii=False)
                response = call_teacher(request, base / "teacher_output_schema.json", base, args.timeout)
                returned = {item["sample_id"]: item for item in response["labels"]}
                expected = {item["sample_id"] for item in batch}
                if set(returned) != expected: raise RuntimeError("teacher response sample IDs do not match batch")
                timestamp = datetime.now(timezone.utc).isoformat()
                for context in batch:
                    label = returned[context["sample_id"]]
                    if context["environment_fields"] == "unavailable" and label["recommended_action"] in {"raise_monitor", "reposition_object"}:
                        raise RuntimeError("teacher invented an unavailable environment action")
                    if context["duration_min"] is None and label["recommended_action"] == "take_break":
                        raise RuntimeError("teacher invented duration evidence")
                    annotations[context["sample_id"]].append({"pass": pass_index + 1, "teacher_model": state["teacher_model"], "timestamp": timestamp, "prompt_version": settings["prompt_version"], "prompt_checksum": prompt_checksum, "context_checksum": context["context_checksum"], "label": label})
    except Exception as exc:
        state.update({"state": "awaiting_teacher", "error": str(exc)})
        (output / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(state, ensure_ascii=False)); return 3

    consensus, rejected = [], []
    minimum_confidence = float(settings["minimum_teacher_confidence"])
    for context in contexts:
        labels = annotations[context["sample_id"]]
        first = labels[0]["label"]
        exact = all((item["label"]["risk_level"], item["label"]["recommended_action"], item["label"]["abstain"]) == (first["risk_level"], first["recommended_action"], first["abstain"]) for item in labels)
        confidence = sum(item["label"]["confidence"] for item in labels) / len(labels)
        record = {"context": context, "annotations": labels, "consensus_confidence": confidence}
        if exact and confidence >= minimum_confidence and not first["abstain"]:
            record["teacher_label"] = first; consensus.append(record)
        else:
            record["rejection_reasons"] = [reason for condition, reason in ((not exact, "teacher_disagreement"), (confidence < minimum_confidence, "low_confidence"), (first["abstain"], "teacher_abstained")) if condition]
            rejected.append(record)
    result = {"state": "labeled", "source": "real_MultiPosture_observations", "teacher_model": state["teacher_model"], "prompt_version": settings["prompt_version"], "prompt_checksum": prompt_checksum, "attempted": len(contexts), "consensus": consensus, "rejected": rejected, "coverage": len(consensus) / len(contexts)}
    (output / "labels.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "state.json").write_text(json.dumps({k: result[k] for k in ("state", "attempted", "coverage")}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"state": "labeled", "attempted": len(contexts), "accepted": len(consensus), "coverage": result["coverage"]}, ensure_ascii=False)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
