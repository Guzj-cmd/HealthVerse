# HealthVerse Pose Classifier

- Evaluation status: **passed**
- Selected estimator: `random_forest`
- Independent test accuracy (conditional on detected pose): `0.9196`
- Independent test Macro-F1 (conditional on detected pose): `0.9440`
- Pose coverage before filtering: `unreported`
- Split unit: subject_id (no subject appears in more than one partition)

## Per-class recall

- LAP: 0.893
- LCL: 1.000
- LCR: 1.000
- LCS: 0.933
- LLL: 1.000
- LLR: 1.000
- LWA: 0.795

## Intended use

Classify user-defined posture states from MediaPipe 33-point landmarks. It is not a medical diagnostic model. The status is `passed` only when every configured threshold, including pose coverage, is met on the untouched test partition.

## Data and limitations

Dataset: `multiposture-lower.jsonl`. Review `splits.csv`, label provenance, consent, camera placement, demographics, and failure cases before deployment. A pass on one dataset does not imply clinical validity or cross-domain generalization.
