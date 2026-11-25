# HealthVerse dataset expansion

This project expands data only when the source is real, its use terms are known, and the evaluation can prevent participant or dataset leakage. Raw third-party datasets are downloaded to ignored local cache directories and are not redistributed in this repository.

## What is trained now

- **MultiPosture** supplied 4,800 expert-labelled skeleton frames from 13 participants for the existing fine-grained upper- and lower-body sitting-posture experiments. Those experiments use participant-disjoint evaluation, but the Zenodo Rights/License field is blank. New training and further weight redistribution are held until the authors clarify permitted use.
- **Edinburgh Office** supplies 456,714 labelled fixed-camera frames from four participants in four real offices. A detector-box geometry context head was trained and evaluated by holding out an entire office and participant. It was **rejected**: 0.5814 accuracy, 0.6050 macro-F1, and 0.2128 sitting recall failed the 0.80/0.80/0.50 quality gate. No deployable artifact is emitted or integrated; the result shows that bounding-box geometry alone does not transfer reliably across offices.
- **BEHAVE (CVPR 2022)** supplies 51 selected human–object sequences from seven participants for a separate transform-based interaction head. Leave-one-participant-out evaluation reached 0.9310 accuracy and 0.9077 macro-F1 for seated contact, table lean and monitor interaction. Every aggregate class recall exceeded 0.88, so the predefined macro-F1 ≥ 0.85 and per-class recall ≥ 0.80 gate passed. These are source-derived interaction labels, not health outcomes.

The two tasks are intentionally separate. The existing MultiPosture experiment asks “how is the seated body configured?”; Edinburgh Office asks “what coarse office state is observable?”. The latter must not be presented as a medical diagnosis or a fine-grained ergonomic score.

## Next relationship datasets

1. **BEHAVE's current auxiliary head** uses official 30fps fitted transforms, not raw camera pixels. The next step is a camera-side person/object detector that produces an equivalent relation input.
2. **PROX (ICCV 2019)** adds human–scene contact, distance and occlusion robustness across twelve scanned indoor scenes.
3. **Aria Digital Twin (ICCV 2023)** can later supply gaze targets and temporal work context, but its egocentric camera domain is not used as a substitute for HealthVerse's fixed camera.

PROX and Aria Digital Twin need their own license/registration steps and task-specific adapters before training. None of these sources is silently merged with posture labels.

## Held or access-gated sources

- **HuMoLs** adds 101 real motionless-person videos across home, office, lab, indoor and outdoor scenes. Its official masks were used for a nested video-level silhouette experiment. The model was rejected because macro-F1 was 0.5827 and standing recall was 0.0; the release has no participant ID and only four standing videos. This negative result is retained as evidence, not deployed.
- **NICR Multi-Task Dataset** is highly relevant (27 participants, 235k depth patches, official participant-disjoint split), but the dataset requires an institutional signature and an emailed access request.
- **MultiPosture** is openly downloadable, but its Zenodo Rights/License field does not name a license. Existing result records are retained for reproducibility; the source file is not redistributed and no new release is produced until permission is clarified.
- **SitPose** describes 36 participants in the paper, but the public repository snapshot inspected here contains 5,746 derived-angle rows, no participant identifier, and no explicit dataset license. It is held out of formal metrics until the authors clarify the release.
- **COUCH (ECCV 2022)** was audited using the official lightweight MoCap archive: 485 sequences, 656,698 frames and six subjects across three chairs and one sofa. The archive is intact and every sequence has a valid `start_idx/end_idx` interval, but its NPZ schema contains no hand-contact/interaction target and no official sequence-to-contact manifest accompanies the download. The paper's right-hand/left-hand/both-hands/no-contact/free-interaction/locomotion taxonomy therefore cannot be recovered without guessing from filenames or geometry. Training is blocked, zero LOSO folds were run, and no model or accuracy was produced. The reusable audit is recorded in `runs/couch-mocap-audit-v1/`.

## Source records

- MultiPosture: <https://zenodo.org/records/14230872>
- Edinburgh Office: <https://homepages.inf.ed.ac.uk/rbf/OFFICEDATA/>
- BEHAVE: <https://virtualhumans.mpi-inf.mpg.de/behave/>
- PROX: <https://prox.is.tue.mpg.de/>
- Aria Digital Twin: <https://facebookresearch.github.io/projectaria_tools/docs/open_datasets/aria_digital_twin_dataset>
- NICR Multi-Task: <https://github.com/TUI-NICR/nicr-multi-task-dataset>
- HuMoLs: <https://datashare.ed.ac.uk/handle/10283/8851>
- SitPose: <https://github.com/TaylorDurden1114/SitPose>
- COUCH: <https://virtualhumans.mpi-inf.mpg.de/couch/>

The machine-readable status, license, sample scale, target task, and evaluation protocol are recorded in `datasets.registry.json`.
