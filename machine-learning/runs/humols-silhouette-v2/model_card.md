# HuMoLs silhouette robustness model

## Intended use

Auxiliary classification of a supplied binary person silhouette as `lying`, `sitting`, or `standing`. This experiment tests pose-shape robustness across the real HuMoLs scenarios and camera views. It is not the HealthVerse fine-grained sitting model and is not a medical diagnosis.

## Data and protocol

- 101 official HuMoLs videos, represented by the one official person mask released for each video.
- Nested evaluation: four stratified outer folds and three stratified inner folds for model selection.
- Raw RGB videos were not used or redistributed.
- Pooled outer-CV accuracy: **0.9109**
- Pooled outer-CV macro-F1: **0.5827**
- Per-class recall: {"lying": 0.6666666666666666, "sitting": 1.0, "standing": 0.0}

## Critical limitations

The release has no participant identifier, so no participant-disjoint claim is possible. The official description calls the release single-subject, while the table contains both M/F metadata. There are only four standing videos. Results are therefore descriptive scene/view robustness evidence only. Inference also assumes a foreground silhouette supplied by an upstream segmentation model.

## Quality gate

Status: **REJECTED**. The acceptance gate requires macro-F1 >= 0.80 and every class recall >= 0.50. A rejected artifact is retained only to document the real experiment and must not be integrated as a production model.

Source: <https://datashare.ed.ac.uk/handle/10283/8851>. The official description permits free use with citation and asks users to cite OPPH (ACVR/ECCV Workshop 2024).
