# BEHAVE relation v2 model card

## Nested evaluation

Every outer fold freezes one complete participant. Candidate selection happens only in a 3-fold GroupCV over the remaining participants. The outer participant is evaluated once after selection. The fixed selection order is macro-F1, minimum class recall, accuracy, then lower predefined complexity rank.

## Result

- Nested LOSO accuracy: **0.9624**
- Nested LOSO macro-F1: **0.9482**
- Minimum aggregate class recall: **0.8631**
- Per-class recall: {"seated_contact": 0.9868055555555556, "table_lean": 0.8630952380952381, "monitor_interaction": 0.9598214285714286}
- Quality gate: **PASSED**
- v1 macro-F1: 0.9077; delta: +0.0405
- v1 minimum recall: 0.8810; delta: -0.0179
- Deployment candidate under the predeclared replacement rule: **V1**

## Temporal feature ablation

The temporal representation adds causal 15-frame rolling statistics for joint angular speed, person-object relative velocity, and object angular velocity. `ablation_summary.csv` records every inner-only comparison; no candidate is selected from outer test performance.

## License boundary

BEHAVE permits non-commercial scientific research. Raw fits are excluded from Git. The fitted `model.joblib` remains local and Git-ignored pending clarification of derived-weight redistribution.

## Limitations

- Interaction labels come from BEHAVE sequence names, not ergonomic or medical outcome annotations.
- Temporal statistics are causal past-only windows, but input still requires fitted SMPL and object transforms.
- Sub08 has no table_lean test support; aggregate outer predictions contain all classes.
- Nested selection prevents direct outer-test tuning, but seven participants still yield wide uncertainty.
