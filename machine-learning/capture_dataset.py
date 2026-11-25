from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

from hvml.io import PoseSample, write_jsonl_sample


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture labeled MediaPipe landmarks from a camera or video.")
    parser.add_argument("--source", default="0", help="Camera index or video path")
    parser.add_argument("--subject-id", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--stride", type=int, default=5)
    parser.add_argument("--max-samples", type=int, default=500)
    args = parser.parse_args()
    try:
        import cv2
        import mediapipe as mp
    except ImportError:
        print("Install capture dependencies from requirements.txt", file=sys.stderr); return 3
    source = int(args.source) if args.source.isdigit() else args.source
    capture = cv2.VideoCapture(source)
    if not capture.isOpened(): raise RuntimeError(f"cannot open input: {args.source}")
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
    count = frame_index = frames_with_pose = 0
    pose = mp.solutions.pose.Pose(static_image_mode=False, model_complexity=1, min_detection_confidence=0.5, min_tracking_confidence=0.5)
    try:
        with output.open("a", encoding="utf-8") as handle:
            while count < args.max_samples:
                ok, frame = capture.read()
                if not ok: break
                frame_index += 1
                result = pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                if result.pose_landmarks:
                    frames_with_pose += 1
                if frame_index % max(1, args.stride) == 0 and result.pose_landmarks:
                    landmarks = np.asarray([[p.x, p.y, p.z, p.visibility] for p in result.pose_landmarks.landmark], dtype=float)
                    sample_id = f"{args.subject_id}-{int(time.time() * 1000)}-{frame_index}"
                    write_jsonl_sample(handle, PoseSample(sample_id, args.subject_id, args.label, str(args.source), landmarks)); count += 1
                cv2.putText(frame, f"{args.label} samples: {count}", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (40, 220, 120), 2)
                cv2.imshow("HealthVerse capture - press q to stop", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"): break
    finally:
        pose.close(); capture.release(); cv2.destroyAllWindows()
    print(f"captured {count} samples to {output}")
    manifest_path = output.with_suffix(".capture-metrics.json")
    previous = {"frames_total": 0, "frames_with_pose": 0, "samples_saved": 0}
    if manifest_path.is_file():
        previous.update(json.loads(manifest_path.read_text(encoding="utf-8-sig")))
    totals = {
        "frames_total": int(previous["frames_total"]) + frame_index,
        "frames_with_pose": int(previous["frames_with_pose"]) + frames_with_pose,
        "samples_saved": int(previous["samples_saved"]) + count,
    }
    totals["pose_coverage"] = totals["frames_with_pose"] / max(1, totals["frames_total"])
    manifest_path.write_text(json.dumps(totals, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"pose coverage: {totals['pose_coverage']:.3f}; manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
