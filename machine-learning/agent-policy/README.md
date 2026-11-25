# HealthVerse Agent Policy

This folder implements the current auditable path:

1. train posture perception on real MultiPosture participant data;
2. select real participant rows by subject/posture strata;
3. call the locally configured AI teacher twice with a strict JSON schema;
4. reject disagreement, low-confidence, and abstained labels without rule fallback;
5. distill accepted teacher labels into lightweight action/risk students with subject-disjoint splits.

## Current status

- Perception benchmark: passed on the configured participant-held-out split, Accuracy `0.9853`, Macro-F1 `0.9838`.
- Teacher v2: 127 real contexts, 119 exact-consensus labels, coverage `0.9370`.
- Student v2: development-passed teacher agreement, action Accuracy/Macro-F1 `1.0000/1.0000` and risk Accuracy/Macro-F1 `1.0000/1.0000`.
- These student numbers are **agreement with an AI teacher**, not medical accuracy. v2 reused the development participant split after v1 failure and requires a future new-participant external test.
- Environment policy: untrained. Missing monitor position, object reach, and duration values are never invented.

## Reproduce

From this directory, with the real MultiPosture CSV available:

```powershell
python train_perception.py --data <multiposture.csv> --output artifacts/perception --config config-v2.json
python label_teacher.py --data <multiposture.csv> --output artifacts/teacher-v2 --config config-v2.json --batch-size 24
python train_student.py --data <multiposture.csv> --labels artifacts/teacher-v2/labels.json --output artifacts/student-v2 --config config-v2.json
python -m unittest discover -s tests -v
```

`label_teacher.py` invokes `codex exec` using local authentication/configuration, read-only sandboxing, an ephemeral session, and `teacher_output_schema.json`. It never reads or prints a token. If the local teacher is unavailable, it writes `awaiting_teacher` and exits without generating labels.

## Runtime contract

The learned posture model supplies pose context. The distilled student selects only actions represented by supported teacher labels. `policy.py` applies independent safety constraints after scoring. An LLM may verbalize the frozen action but cannot choose or change it.

The pairwise preference schema/server and reward-model script are retained as future real-feedback infrastructure. They are not part of the current pass condition and cannot train without consented human records.

See `iteration_history.md`, `DATA_MANIFEST.md`, `artifacts/perception/model_card.md`, and `artifacts/student-v2/model_card.md`.

## Evidence safety gate (BEHAVE)

`evidence_gate.py` adds a narrower integration contract for passed BEHAVE relation evidence. It emits only `no_action` or `ask_confirm`; invalid, unsupported, or low-confidence evidence always requests confirmation. The frozen aggregate evaluation is in `artifacts/evidence-gate-v1/metrics.json` and the exact input/output boundary is in `evidence_gate_contract.json`.

This result does **not** complete the recommendation Agent. The accepted set contains 47 sequences from seven participants but only two `ask_confirm` examples and no mutating-action examples. Concrete suggestions still require real environment measurements, sustained-duration evidence, user preference, and action-outcome labels across participants. Per-sequence teacher outputs and the BEHAVE-derived weight are intentionally excluded from this public evidence package.
