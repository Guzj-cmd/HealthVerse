# BEHAVE evidence safety gate

This head maps structured evidence from a **passed upstream relation model** to `no_action` or `ask_confirm`. It is a safety refusal/request-confirmation gate, not a complete health or ergonomic recommendation Agent.

## Evaluation

- 47 accepted sequences from seven real BEHAVE participants; subject leave-one-out evaluation.
- Accuracy `0.9574`; Macro-F1 `0.8220`.
- Participant-cluster bootstrap 95% CI: Accuracy `[0.9149, 1.0000]`; Macro-F1 `[0.4824, 1.0000]`.
- Brier score `0.0364`; five-bin ECE `0.1074`.
- Labels contain 45 `no_action` and only two `ask_confirm` examples.

The aggregate metrics are tracked in `metrics.json`. Per-sequence teacher outputs and the BEHAVE-derived model weight are not included.

## Runtime boundary

Unknown relations, missing objects, invalid consistency, unpassed upstream evidence, unsupported learned actions, and confidence below `0.70` all return `ask_confirm`. The head cannot emit `raise_monitor`, `reposition_object`, or `take_break`.

## Limitations

The data do not contain the environmental measurements, sustained-duration evidence, user preference, or outcome labels needed to evaluate concrete advice. The two positive examples and wide clustered Macro-F1 interval are insufficient for a full advice claim.
