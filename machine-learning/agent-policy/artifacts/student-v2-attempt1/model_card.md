# HealthVerse distilled student model card

- Status: **failed**
- Training observations: 119 real MultiPosture participant samples
- Teacher: `gpt-5.6-sol`, two-pass exact consensus
- Teacher-label coverage: 0.9370
- Action student: `random_forest`
- Held-out action Accuracy: 0.7407
- Held-out action Macro-F1: 0.6769
- Risk student: `logistic_regression`
- Held-out risk Accuracy: 0.8519
- Held-out risk Macro-F1: 0.8355

All reported predictive metrics measure agreement with filtered AI-teacher labels on participant-held-out real observations. They are not medical accuracy, clinical validity, or proof that the advice improves health. Only `no_action` and `ask_confirm` received supported teacher labels. Environment-dependent actions remain untrained because MultiPosture has no observed monitor/object relation or duration fields.
