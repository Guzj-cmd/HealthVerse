# CHI/IMWUT-Inspired Posture Model

- Result: **未达到 100%，保留真实误差并停止在无泄漏的最佳候选**
- Selected model: `extra_trees_half_features`
- Development GroupKFold Accuracy / Macro-F1: `0.9278` / `0.9398`
- Frozen subject-disjoint test Accuracy / Macro-F1: `0.9347` / `0.9598`
- Test subjects: `subject-13, subject-3, subject-5`

## Method

The representation follows EduSense: body-scale normalization and pairwise keypoint direction/distance features. HealthVerse also includes normalized MediaPipe coordinates, visibility, and interpretable joint/lean angles. Candidate selection uses GroupKFold over development subjects. The frozen test subjects are evaluated only after a winner is selected.

## Claim boundary

This is real training on MultiPosture landmarks, not simulated metrics. It is conditional on a pose being detected and is not a medical diagnostic model. The 13-participant dataset is too small to establish universal performance; an untouched external participant cohort remains necessary.
