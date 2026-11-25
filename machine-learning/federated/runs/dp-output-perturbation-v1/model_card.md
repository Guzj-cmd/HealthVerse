# Sample-DP output perturbation: rejected result

This attempted a second formally accounted privacy mechanism: Gaussian output perturbation of an L2-regularized strongly convex softmax ERM, using 512 fixed public random ReLU features with feature norm bounded by one.

The run used replace-one sample-level central DP with `epsilon=6`, `delta=1e-5` and zCDP-to-approximate-DP accounting. The sensitivity bound was `4*sqrt(2)/(n*lambda)`, with `lambda=0.05`. Optimizer final gradient norms were at most `5.04e-8`.

The mechanism was rejected: private and non-private versions both collapsed to the majority class, with Accuracy `0.5882`, Macro-F1 `0.2469`, and zero recall for `table_lean` and `monitor_interaction`, below the `0.65` Macro-F1 gate. No model weight is released.

The guarantee is sample-level trusted-curator DP, not participant-level DP, local DP, secure aggregation, or a private federated system. Correlated frames make sample-level protection materially weaker than participant-level protection for this dataset.
