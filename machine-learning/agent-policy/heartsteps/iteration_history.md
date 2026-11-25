# HeartSteps evidence-policy iteration history

## Candidate v1 — preprocessing failure

- Protocol was frozen in `protocol.json` before this run.
- The source CSV SHA-256 matched the frozen value.
- The run stopped before fitting any outcome model because fields documented as numeric contain the literal string `unknown` in the public release.
- Error: median imputation could not convert `unknown` to a float.
- Correction: coerce every declared numeric feature with `errors="coerce"`; the already frozen median imputer then handles those cells as missing values.
- No metric, threshold, split, or quality gate was changed after observing the failure.

## Candidate v1 — nonlinear T-learner

- Outcome model: two cross-fitted ExtraTrees regressors, one per randomized action.
- Participants: 37; planned, available, internally consistent decision points: 6,112.
- Learned-policy doubly robust uplift versus never suggest: `+0.055893` log-steps.
- Suggestion rate: `0.505890`; matched-policy effective sample size: `2,985.60`.
- Participant-cluster bootstrap 95% CI: `[-0.026892, 0.144031]`.
- Status: **REJECTED** because the frozen lower confidence bound must be greater than zero.
- The output remains in `build/candidate-v1`; no deployable weight was written.

## Candidate v2 — low-variance linear action model

- Motivation fixed before running: Personalized HeartSteps uses a deliberately low-dimensional linear treatment-effect model to reduce variance; a regularized linear T-learner is a distinct mechanism from candidate v1.
- Change: replace ExtraTrees with separate Ridge outcome models (`alpha=10`) while retaining the exact data, outer folds, inner threshold selection, DR estimator, bootstrap, and gates.
- Result: **PASSED**.
- Cross-fitted learned-policy DR value: `3.219136` log-steps.
- Never-suggest DR value: `3.109960`; uplift `+0.109175`.
- Always-suggest DR value: `3.216620`; the learned policy is not claimed superior to always suggest because that difference was not a frozen gate and has no dedicated confidence interval.
- Participant-cluster bootstrap 95% CI for uplift versus never suggest: `[0.004604, 0.213432]`.
- Suggestion rate: `0.625327`; matched-policy effective sample size: `3,059.83`.
- All five outer folds have zero participant overlap. The final artifact was fitted only after frozen cross-fitted evaluation passed.

