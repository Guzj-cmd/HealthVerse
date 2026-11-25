# HealthVerse distilled student model card

- Status: **passed**
- Training observations: 119 real MultiPosture participant samples
- Teacher: `gpt-5.6-sol`, two-pass exact consensus
- Teacher-label coverage: 0.9370
- Action student: `logistic_regression`
- Held-out action Accuracy: 1.0000
- Held-out action Macro-F1: 1.0000
- Risk student: `logistic_regression`
- Held-out risk Accuracy: 1.0000
- Held-out risk Macro-F1: 1.0000

All reported predictive metrics measure agreement with filtered AI-teacher labels on participant-held-out real observations. They are not medical accuracy, clinical validity, or proof that the advice improves health. Only `no_action` and `ask_confirm` received supported teacher labels. Environment-dependent actions remain untrained because MultiPosture has no observed monitor/object relation or duration fields.
