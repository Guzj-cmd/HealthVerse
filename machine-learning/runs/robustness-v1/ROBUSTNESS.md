# MultiPosture Robustness Analysis

All uncertainty resampling is clustered by `subject_id`; frames are never bootstrapped independently.

## Coverage boundary

MultiPosture contains landmark rows after successful extraction, not the original stream with failed detections. Pose coverage is therefore **N/A**, and the end-to-end status is **not evaluated**.

## upper_body

- Classifier status: `classifier_passed`
- End-to-end status: `end_to_end_not_evaluated`
- Fixed estimator for GroupKFold: `hist_gradient_boosting`
- Held-out Accuracy: 0.9899 (subject-cluster 95% CI 0.9875–0.9932)
- Held-out Macro-F1: 0.9880 (95% CI 0.7966–0.9946)
- Held-out Balanced Accuracy: 0.9917 (95% CI 0.7957–0.9947)
- GroupKFold pooled Macro-F1: 0.9755
- Worst unseen subject group: `subject-12|subject-3|subject-8`; Macro-F1 0.9467; Balanced Accuracy 0.9338

## lower_body

- Classifier status: `classifier_passed`
- End-to-end status: `end_to_end_not_evaluated`
- Fixed estimator for GroupKFold: `random_forest`
- Held-out Accuracy: 0.9196 (subject-cluster 95% CI 0.8176–1.0000)
- Held-out Macro-F1: 0.9440 (95% CI 0.8145–1.0000)
- Held-out Balanced Accuracy: 0.9460 (95% CI 0.8271–1.0000)
- GroupKFold pooled Macro-F1: 0.9385
- Worst unseen subject group: `subject-10|subject-4|subject-7`; Macro-F1 0.8997; Balanced Accuracy 0.8969

## Interpretation

These results measure classification conditional on an available 33-point landmark record. They do not establish camera-stream coverage, clinical validity, or performance on a new camera/domain.
