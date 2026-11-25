# Agent policy iteration history

All posture contexts below come from real MultiPosture v1 participant rows. AI-teacher labels are stored with model, timestamp, prompt version, prompt checksum, and context checksum. No rule-generated or synthetic posture records were used.

| Iteration | Real contexts | Exact two-pass consensus | Student input | Participant-held-out action Accuracy | Macro-F1 | Result |
|---|---:|---:|---|---:|---:|---|
| v1 | 64 | 58 (90.625%) | 99 MediaPipe coordinates | 0.7692 | 0.7068 | Failed Accuracy ≥ 0.80 |
| v2 attempt 1 | 127 | 119 (93.7008%) | 99 MediaPipe coordinates | 0.7407 | 0.6769 | Failed both action gates |
| v2 attempt 2 | 127 | 119 (93.7008%) | Same structured posture context shown to teacher | 1.0000 | 1.0000 | Development-passed |

## What changed

v1 → v2 increased each available subject/posture stratum from one to two observed center samples. Existing annotations were reused only when both context and prompt checksums matched; all new samples received two real local-Agent calls. Eight v2 samples were removed for teacher disagreement; none were replaced.

v2 attempt 1 → attempt 2 changed only the student representation. The teacher saw observed posture labels and derived geometric angles, while attempt 1 forced the student to relearn this semantic layer from 99 coordinates using 119 examples. Attempt 2 distills the same observable structured context. Model and binary threshold were chosen on validation participants only.

## Interpretation boundary

The v2 result is **teacher agreement**, not medical correctness, ergonomic validity, or real-world benefit. Because v1 exposed the same held-out subjects and v2 development responded to that failure, v2 is a development result rather than a fresh independent external test. A future release must test on newly recruited participants and real camera conditions before making deployment claims.

Only `ask_confirm` (95) and `no_action` (24) had supported v2 teacher labels. `raise_monitor`, `reposition_object`, and `take_break` remain untrained because MultiPosture has no observed monitor/object relation or sitting-duration fields.
