# HealthVerse Federated Posture Model

- Status: **failed**
- Run type: `local_federated_test`
- Dataset: `multiposture-upper.jsonl` (real MultiPosture participant landmarks)
- Split: unseen participants; train 7, validation 3, test 3
- FedAvg test accuracy: 0.9238
- FedAvg test Macro-F1: 0.8988
- Centralized baseline Macro-F1: 0.9485
- Uploaded parameter bytes: 13181000

## Per-class recall

- TLB: 0.4943
- TLF: 0.9875
- TLL: 1.0000
- TLR: 1.0000
- TUP: 0.8904

## Privacy and claim boundary

Raw landmarks never enter the aggregator in this simulation; only clipped parameter updates are averaged. Secure aggregation is not implemented, differential privacy is disabled, and epsilon is therefore not applicable. This run simulates subject clients on one computer and must not be described as a real multi-device deployment.
