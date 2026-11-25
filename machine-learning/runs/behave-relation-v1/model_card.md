# BEHAVE relation model card

## Intended task

Auxiliary classification of three observed human-object interaction states from fitted body/object transforms: `seated_contact`, `table_lean`, and `monitor_interaction`. This is not a medical model and does not assign ergonomic risk.

## Real data and split

- Source: [BEHAVE: Dataset and Method for Tracking Human Object Interactions, CVPR 2022](https://virtualhumans.mpi-inf.mpg.de/behave/)
- Participants used: 7 (Sub01, Sub02, Sub03, Sub04, Sub06, Sub07, Sub08)
- Sequences: 51
- Subsampled frames: 2448 (48 maximum per sequence)
- Evaluation: leave one complete `SubXX` participant out. Shape/identity parameters (`betas`) are excluded.

## Held-out-participant result

- Aggregate accuracy: **0.9310**
- Aggregate macro-F1: **0.9077**
- Per-class recall: {"seated_contact": 0.9263888888888889, "table_lean": 0.8809523809523809, "monitor_interaction": 0.9657738095238095}
- Quality gate: **PASSED** (macro-F1 ≥ 0.85; every aggregate class recall ≥ 0.8)
- Fold mean accuracy: 0.9450 ± 0.0467
- Fold mean macro-F1 over classes present in each test subject: **0.9329 ± 0.0584**

## License and artifact boundary

BEHAVE is licensed for non-commercial scientific research. Source files are not redistributed. The fitted `model.joblib` is generated locally and ignored by Git pending explicit clarification that derived weights may be redistributed. Its SHA-256 is recorded in `metrics.json`.

## Limitations

- Labels are source-derived interaction categories from sequence names, not ergonomic risk or medical outcome labels.
- Frames are subsampled evenly per sequence; LOSO prevents identity leakage, but adjacent moments from one sequence remain correlated within one fold.
- Sub08 has no table_lean sequence, so that fold has zero support for table_lean; aggregate LOSO includes all classes.
- The input requires fitted SMPL/object transforms and is not yet a raw-RGB browser model.
