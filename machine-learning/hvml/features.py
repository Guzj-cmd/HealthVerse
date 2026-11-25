from __future__ import annotations

import numpy as np

from . import FEATURE_SCHEMA_VERSION


ANGLE_TRIPLETS = (
    (11, 13, 15), (12, 14, 16),  # elbows
    (11, 23, 25), (12, 24, 26),  # hips/trunk
    (23, 25, 27), (24, 26, 28),  # knees
    (7, 11, 23), (8, 12, 24),    # ear/shoulder/hip (neck-trunk)
)

# Stable upper-body/leg points used for EduSense-style pairwise direction and
# scale-normalized distance features. Keeping a subset limits dimensionality.
PAIRWISE_JOINTS = (0, 7, 8, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26)


def _angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    left, right = a - b, c - b
    denominator = np.linalg.norm(left) * np.linalg.norm(right)
    if denominator < 1e-9:
        return 0.0
    cosine = np.clip(float(np.dot(left, right) / denominator), -1.0, 1.0)
    return float(np.arccos(cosine) / np.pi)


def pose_features(landmarks: np.ndarray) -> np.ndarray:
    points = np.asarray(landmarks, dtype=np.float64)
    if points.shape != (33, 4):
        raise ValueError("expected MediaPipe landmarks with shape (33, 4)")
    xyz, visibility = points[:, :3], np.clip(points[:, 3], 0.0, 1.0)
    hip_center = (xyz[23] + xyz[24]) / 2.0
    shoulder_center = (xyz[11] + xyz[12]) / 2.0
    torso = float(np.linalg.norm(shoulder_center - hip_center))
    shoulder_width = float(np.linalg.norm(xyz[11] - xyz[12]))
    scale = max(torso, shoulder_width, 1e-4)
    normalized = (xyz - hip_center) / scale

    angles = [_angle(normalized[a], normalized[b], normalized[c]) for a, b, c in ANGLE_TRIPLETS]
    shoulder_line = float(np.arctan2(normalized[12, 1] - normalized[11, 1], normalized[12, 0] - normalized[11, 0]) / np.pi)
    hip_line = float(np.arctan2(normalized[24, 1] - normalized[23, 1], normalized[24, 0] - normalized[23, 0]) / np.pi)
    trunk_vector = shoulder_center - hip_center
    trunk_lean = float(np.arctan2(trunk_vector[0], -trunk_vector[1]) / np.pi)
    head_center = (xyz[7] + xyz[8]) / 2.0
    head_vector = head_center - shoulder_center
    neck_lean = float(np.arctan2(head_vector[0], -head_vector[1]) / np.pi)
    engineered = np.asarray([*angles, shoulder_line, hip_line, trunk_lean, neck_lean], dtype=np.float64)
    pairwise = []
    for offset, left_index in enumerate(PAIRWISE_JOINTS):
        for right_index in PAIRWISE_JOINTS[offset + 1:]:
            delta = normalized[right_index] - normalized[left_index]
            distance = float(np.linalg.norm(delta))
            direction = delta / max(distance, 1e-9)
            pairwise.extend([float(direction[0]), float(direction[1]), float(direction[2]), distance])
    return np.concatenate([normalized.reshape(-1), visibility, engineered, np.asarray(pairwise)]).astype(np.float32)


def feature_names() -> list[str]:
    names = [f"{axis}{index}_normalized" for index in range(33) for axis in ("x", "y", "z")]
    names += [f"visibility{index}" for index in range(33)]
    names += [f"joint_angle_{a}_{b}_{c}" for a, b, c in ANGLE_TRIPLETS]
    names += ["shoulder_line", "hip_line", "trunk_lean", "neck_lean"]
    for offset, left_index in enumerate(PAIRWISE_JOINTS):
        for right_index in PAIRWISE_JOINTS[offset + 1:]:
            names += [
                f"pair_{left_index}_{right_index}_dx_unit",
                f"pair_{left_index}_{right_index}_dy_unit",
                f"pair_{left_index}_{right_index}_dz_unit",
                f"pair_{left_index}_{right_index}_distance_normalized",
            ]
    return names


def schema() -> dict[str, object]:
    return {"version": FEATURE_SCHEMA_VERSION, "feature_count": len(feature_names()), "features": feature_names()}
