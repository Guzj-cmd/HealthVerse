# MultiPosture perception model card

- Data: real, expert-validated MultiPosture v1 skeletal frames (Zenodo 14230872)
- Selected on validation: `hist_gradient_boosting`
- Independent participant-held-out test accuracy: `0.9853`
- Independent participant-held-out test Macro-F1: `0.9838`
- Gate: **passed**

## Test recall

- `TLB`: 1.0000
- `TLF`: 0.9881
- `TLL`: 0.9250
- `TLR`: 1.0000
- `TUP`: 0.9924

## Scope

This model recognizes five upper-body sitting-posture labels. It does not recognize monitor/object relations and does not choose recommendations. The 4,794-row downloaded CSV contains 99 numeric MediaPipe coordinates even though the Zenodo prose summarizes an 11-joint subset; this run records the inspected file shape rather than silently assuming the prose shape.

## Limitations

Only 13 participants are present. Subject-disjoint evaluation reduces frame leakage but does not establish demographic, camera, home/office, or clinical generalization. It is not a medical diagnostic model.
