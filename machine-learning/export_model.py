from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

import joblib


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a checksum-addressed deployment bundle.")
    parser.add_argument("--run", required=True, help="Training output directory")
    parser.add_argument("--output", required=True, help="Destination .zip")
    args = parser.parse_args()
    run, destination = Path(args.run), Path(args.output)
    required = ["model.joblib", "metrics.json", "model_card.md", "confusion_matrix.csv", "training_history.json", "splits.csv"]
    for name in required:
        if not (run / name).is_file(): raise FileNotFoundError(run / name)
    metrics = json.loads((run / "metrics.json").read_text(encoding="utf-8"))
    if metrics.get("end_to_end_status") != "end_to_end_passed":
        raise ValueError("refusing to export without both classifier and end-to-end pose-coverage evidence")
    bundle = joblib.load(run / "model.joblib")
    manifest = {"classifier_status": metrics["classifier_status"], "coverage_status": metrics["coverage_status"], "end_to_end_status": metrics["end_to_end_status"], "selected_model": bundle["metadata"]["selected_model"], "feature_schema": bundle["feature_schema"], "files": {}}
    for name in required:
        manifest["files"][name] = hashlib.sha256((run / name).read_bytes()).hexdigest()
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in required: archive.write(run / name, name)
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
