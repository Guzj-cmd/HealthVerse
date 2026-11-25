# HealthVerse distilled student model card

- Status: **failed**
- Training observations: 58 real MultiPosture participant samples
- Teacher: `gpt-5.6-sol`, two-pass exact consensus
- Teacher-label coverage: 0.9062
- Action student: `logistic_regression`
- Held-out action Accuracy: 0.7692
- Held-out action Macro-F1: 0.7068
- Risk student: `logistic_regression`
- Held-out risk Accuracy: 0.8462
- Held-out risk Macro-F1: 0.8056

All reported predictive metrics measure agreement with filtered AI-teacher labels on participant-held-out real observations. They are not medical accuracy, clinical validity, or proof that the advice improves health. Only `no_action` and `ask_confirm` received supported teacher labels. Environment-dependent actions remain untrained because MultiPosture has no observed monitor/object relation or duration fields.
