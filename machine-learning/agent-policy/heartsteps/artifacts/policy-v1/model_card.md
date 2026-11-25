# HeartSteps activity-suggestion policy v1

## What passed

The policy was trained from the CC BY 4.0 HeartSteps V1 micro-randomized trial: 37 participants and 6,112 available, internally consistent decision points within the planned 42-day window. Sending an activity suggestion was randomized with probability 0.6 versus 0.4 for no suggestion. The outcome is `log1p` Jawbone steps in the following 30 minutes.

Five outer folds hold out complete participants. Each outer training set performs its own three-fold participant-grouped threshold selection. The frozen evaluation uses cross-fitted doubly robust policy values with the known randomization probabilities.

- Learned policy value: `3.219136` log-steps
- Never-suggest value: `3.109960`
- Uplift versus never suggest: `+0.109175`
- Participant-cluster bootstrap 95% CI: `[0.004604, 0.213432]`
- Suggestion rate: `0.625327`
- Matched-policy effective sample size: `3059.83`
- Participant overlap: zero in every outer fold

The learned value is only `0.002516` above the always-suggest estimate. This experiment does **not** establish superiority to always suggesting and does not justify claiming that personalization itself is beneficial.

## Integration boundary

The artifact can emit only `no_action` or `offer_activity_suggestion`. `inference.py` adds `ask_confirm` for invalid evidence and blocks suggestions when the user is unavailable or likely in transit. The only permitted message is a dismissible, non-medical prompt for a brief activity break.

The visual seated-relation gate is a conservative HealthVerse integration boundary; it was not part of the HeartSteps randomized trial. Consequently, the randomized effect estimate validates the downstream suggestion component, not the jointly composed camera-to-suggestion pipeline.

## Prohibited claims

This model does not diagnose disease, predict pain, prescribe treatment, adjust furniture, or establish long-term health benefit. HeartSteps outcomes are near-term step counts, not clinical outcomes.
