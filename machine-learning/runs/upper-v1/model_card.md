# HealthVerse Pose Classifier

- Evaluation status: **failed**
- Selected estimator: `hist_gradient_boosting`
- Independent test accuracy: `0.9902`
- Independent test Macro-F1: `0.9907`
- Split unit: subject_id (no subject appears in more than one partition)

## Per-class recall

- TLB: 0.948
- TLF: 0.996
- TLL: 1.000
- TLR: 1.000
- TUP: 0.992

## Intended use

Classify user-defined posture states from MediaPipe 33-point landmarks. It is not a medical diagnostic model. The status is `passed` only when every configured threshold is met on the untouched test partition.

## Data and limitations

Dataset: `multiposture-upper.jsonl`. Review `splits.csv`, label provenance, consent, camera placement, demographics, and failure cases before deployment. A pass on one dataset does not imply clinical validity or cross-domain generalization.
