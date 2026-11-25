# CHI/IMWUT-Inspired Training Iteration

## Protocol frozen before test evaluation

- Data: real MultiPosture MediaPipe landmark records (13 participants).
- Features: EduSense-style body-scale normalization and pairwise keypoint
  directions/distances, plus normalized landmarks, visibility and joint/lean
  angles.
- Development/test boundary: the 10 development participants and 3 test
  participants from `config-subject3.json`.
- Selection: 3-fold `GroupKFold` on development participants only.
- Candidates: 200-tree Random Forest, 250-tree Extra Trees, 200-iteration
  HistGradientBoosting, and RBF SVC (`C=10`).
- The frozen test partition was evaluated only after selecting the best
  development GroupKFold Macro-F1 candidate for each label task.

## Interrupted attempts

The initial 8-candidate x 5-fold run and a slower reduced run were deliberately
stopped because their runtime was incompatible with the requested iteration
speed. They never produced a test score. The interruption notes and any
development-only checkpoints remain in `../chi-inspired-v1-upper/` and
`../chi-inspired-v1-upper-fast/` so the unsuccessful iterations are not hidden.

## Final real results

| Task | Selected candidate | Development GroupKFold Accuracy | Development GroupKFold Macro-F1 | Frozen-test Accuracy | Frozen-test Macro-F1 | 100% reached |
|---|---:|---:|---:|---:|---:|---:|
| Upper posture | HistGradientBoosting | 0.9689 | 0.9703 | 0.9874 | 0.9813 | No |
| Lower posture | Extra Trees | 0.9278 | 0.9398 | 0.9347 | 0.9598 | No |

The new lower-posture result improves over the earlier Random Forest test run
(Accuracy 0.9196, Macro-F1 0.9440). The new upper candidate does not improve on
the earlier HGB test run (Accuracy 0.9899, Macro-F1 0.9880), so deployment should
retain the earlier upper model and may use the new lower model only if its
browser runtime supports Extra Trees.

## Why 100% was not declared

The remaining errors are concentrated in visually similar classes (especially
`LAP` versus `LWA` and upper `TLF`/`TUP` variants). Repeatedly choosing models by
their score on the same three test participants would turn that test set into a
validation set. Reaching 100% through leakage, participant identity shortcuts,
or relabeling errors was therefore rejected. A legitimate next iteration needs
additional independently collected participants and an untouched external test
cohort; it cannot be manufactured from the current 13-person table.

These metrics are conditional on MediaPipe landmarks already being available.
The source table cannot measure camera-to-landmark pose-detection coverage.
