# COUCH MoCap data audit

## Result

Training is **blocked**. The archive is real, intact and suitable for six-subject
isolation, but it does not carry an explicit target for the published hand-contact
taxonomy. No model, accuracy or derived weights were produced.

## Verified scale

- Archive SHA-256: `c0a0569101a75d3c8257bf5cc4d592ae5c72374a9fccbaf9c846af79111520ae`
- Sequences: 485
- Frames: 656698
- Source interval frames: 245033
- Sequence length: 873 / 1234 / 10715 frames (min / median / max)

| Subject | Sequences | Frames |
| --- | ---: | ---: |
| subject1 | 186 | 264414 |
| subject2 | 51 | 64459 |
| subject3 | 59 | 76394 |
| subject4 | 69 | 98490 |
| subject5 | 66 | 86763 |
| subject6 | 54 | 66178 |

## Quality gate

| Check | Result |
| --- | --- |
| zip_crc_valid | PASS |
| archive_sha256_matches | PASS |
| all_expected_subjects_present | PASS |
| all_sequence_schemas_valid | PASS |
| explicit_source_target_present_for_every_sequence | FAIL |
| loso_training_permitted | FAIL |

Blocker: The official lightweight MoCap NPZ archive contains no explicit contact/interaction target array or official sequence-to-label manifest. start_idx/end_idx are retained as source interval metadata, but the release does not define them as hand-contact or ergonomic classes.

The paper's interaction taxonomy is recorded for provenance, but neither chair
names nor motion-name tokens are mapped to it in this archive. Pose geometry and
distance thresholds are not used as labels. `start_idx` and `end_idx` remain
interval metadata because the lightweight release does not document them as
contact or ergonomic classes.

Repository metadata audit: The official code repository contains MotionCapture/Mode.txt for 120 original and mirrored sequences from one named subject using date-based identifiers. It neither covers the six released subject IDs nor provides a join key for the 485 NPZ files, so it is not used as benchmark ground truth.

## Evaluation contract

If an official contact manifest is supplied later, the intended evaluation is
leave-one-subject-out over all six subjects. This audit ran zero folds and reports
no predictive metric; an integrity check is not a model benchmark.

License: [non-commercial scientific research, education, and artistic projects](https://virtualhumans.mpi-inf.mpg.de/couch/license.html). Raw data remains in an
ignored local cache and is not redistributed.
