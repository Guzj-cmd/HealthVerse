# Edinburgh Office Context Model Card

## Purpose

Auxiliary HealthVerse context head for classifying `empty`, `standing_walking`, `sitting`, and `talking` from up to four person bounding boxes produced by a separate detector. It does not replace the MediaPipe fine-posture model.

## Real data and evaluation

- Dataset: University of Edinburgh Office Monitoring Video Dataset, 20 days, four participants in four offices.
- Input used here: all official per-frame ground-truth bounding boxes and activity labels; no generated or simulated samples.
- License: CC BY-NC-SA. Raw dataset files are excluded from Git and are not redistributed.
- Evaluation: nested leave-one-participant-and-office-out. Candidate selection occurs only within the three development groups of each outer fold.
- Evaluated frames: 456,377.
- Final-candidate fitting frames: 189,024 real frames, capped per participant/class to reduce adjacent-frame redundancy. The fitted candidate is discarded when the gate fails.
- Accuracy: 0.581390.
- Macro-F1: 0.605020.
- Quality gate: **REJECTED**.
- Gate thresholds: Accuracy ≥ 0.80, Macro-F1 ≥ 0.80, every-class recall ≥ 0.50.
- Failures: accuracy 0.581390 < 0.80; macro_f1 0.605020 < 0.80; sitting recall 0.212848 < 0.50.

## Important limitation

The dataset contains 337 fallen frames, all from office-1-participant-1. They are excluded from the four-class score because a subject-disjoint fall benchmark is impossible with one positive participant. The model must not be represented as a validated fall detector. Bounding boxes came from ground truth during training/evaluation; production accuracy also depends on the upstream detector.

The official page describes up to three people, while the downloaded annotations contain 57 frames with four annotation rows. The feature contract therefore accepts four boxes rather than silently discarding these records.

## Deployment decision

This run is **not deployable and is not integrated into HealthVerse** when the quality gate is rejected. The best research candidate was `extra_trees`, but no model artifact is emitted after a failed gate. Improving unseen-office generalization requires image/pose evidence or scene calibration, not merely more tuning of bounding-box geometry.
