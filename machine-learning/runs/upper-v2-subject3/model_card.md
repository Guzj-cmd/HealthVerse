# HealthVerse Pose Classifier

- Evaluation status: **passed**
- Selected estimator: `hist_gradient_boosting`
- Independent test accuracy (conditional on detected pose): `0.9899`
- Independent test Macro-F1 (conditional on detected pose): `0.9880`
- Pose coverage before filtering: `unreported`
- Split unit: subject_id (no subject appears in more than one partition)

## Per-class recall

- TLB: 0.989
- TLF: 1.000
- TLL: 1.000
- TLR: 1.000
- TUP: 0.970

## Intended use

Classify user-defined posture states from MediaPipe 33-point landmarks. It is not a medical diagnostic model. The status is `passed` only when every configured threshold, including pose coverage, is met on the untouched test partition.

## Data and limitations

Dataset: `multiposture-upper.jsonl`. Review `splits.csv`, label provenance, consent, camera placement, demographics, and failure cases before deployment. A pass on one dataset does not imply clinical validity or cross-domain generalization.
