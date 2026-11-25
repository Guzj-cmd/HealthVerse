# Data manifest

## Executed data

- **MultiPosture v1**, DOI `10.5281/zenodo.14230872`: 4,794 real participant frames, 13 participants, expert-validated upper/lower sitting-posture labels. The inspected CSV has 99 numeric MediaPipe coordinates plus subject and two labels.
- License/provenance and the source checksum must be reviewed before redistribution. This package stores trained artifacts, split manifests, selected-row indices, context checksums, and teacher audit records; it does not relabel generated poses as people.

## Teacher labels

- Teacher: local Codex configuration (`gpt-5.6-sol` during this run).
- Prompt: `teacher_prompt.md`, checksum recorded in every annotation.
- Two independent passes per real context; exact agreement required for risk/action/abstention and average confidence ≥ 0.70.
- v2: 127 attempted, 119 accepted, 8 rejected for disagreement.
- Environment and duration were absent and remained absent; environment-dependent actions are not trained.

## Relevant public data not used as office-policy evidence

- SAFELIFT (Zenodo 18243098) contains real, consented lifting videos and ergonomic annotations, but its lifting domain and CC BY-NC-SA license do not establish office-sitting policy performance.
- Anthropic HH-RLHF and AllenAI MultiPref are real general-language preference resources. They are domain-mismatched and were not used to report office-posture recommendation metrics.
- The future pairwise preference collector in this folder remains outside the current pass gate.
