# Scene-specialist relation ensemble v1

## Intended use

Evaluate whether seven observable person/environment relation labels transfer jointly to unseen residential scenes and unseen participants.

## Data and split

- Source: official Charades training annotations and official RGB fc7 features.
- Official Charades test split: not loaded or reused.
- Outer evaluation: each of the five largest scenes is held out.
- Leakage control: every participant appearing in the target scene is removed from all source-scene specialist training.
- Weight selection: each specialist is scored only on the other source scenes; target labels cannot affect its frozen weight.

## Result

The ensemble reaches aggregate macro-mAP `0.3694559494`, versus `0.2614321056` for the frozen baseline. Every held-out scene exceeds the predeclared `0.25` macro-mAP floor and the aggregate exceeds `0.35`. The frozen metrics file is the authoritative record.

## Limitations

- This is evaluation-time cross-validation, not a universal model for arbitrary new scenes.
- Several rare relations have poor recall at threshold `0.5`; macro-mAP is the predeclared primary metric.
- The model consumes official precomputed fc7 features, not live camera frames.
- No health outcome, diagnosis, intervention, or causal recommendation is learned.
- The result does not replace the separate raw-RGB objective-1 model.
