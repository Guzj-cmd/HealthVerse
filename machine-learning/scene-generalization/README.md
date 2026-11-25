# Cross-scene relation generalization

This module reproduces the only objective-3 candidate that passed its frozen gate. It evaluates seven observable human/environment relations on the official Charades **training** split while jointly holding out a residential scene and every participant appearing in that scene. The official test split is never loaded.

The passing candidate trains independent specialists on source scenes. Each specialist receives a weight from its macro-mAP on the other source scenes only. The held-out target labels are read only after all weights are frozen.

## Frozen result

- Aggregate macro-mAP: `0.3694559494`
- Frozen baseline macro-mAP: `0.2614321056`
- Improvement: `+0.1080238438`
- Five held-out scene macro-mAP values: `0.2746`, `0.2775`, `0.2738`, `0.3240`, `0.4831`
- Subject overlap in every fold: `0`
- Gate: aggregate `>= 0.35`, every scene `>= 0.25`, at least four supported classes per scene
- Status: `PASSED`

The exact fold records are in `artifacts/scene-specialist-v1/metrics.json`. The rejected fixed-model baseline is retained in `baseline_metrics.json`.

## Reproduction

The scripts require official Charades train annotations, the separately downloaded official RGB fc7 feature bundle, and `../datasets/charades-relation.json`. Large licensed feature caches are intentionally not committed.

```powershell
python run_scene_generalization.py --annotations <Charades_v1_train.csv> --features <rgb_features.npz> --config ..\datasets\charades-relation.json --output baseline.json
python run_scene_specialist_ensemble.py --annotations <Charades_v1_train.csv> --features <rgb_features.npz> --config ..\datasets\charades-relation.json --baseline baseline.json --output specialist.json
```

## Scope

This is a relation-recognition generalization result, not a health-outcome model. It does not establish causal benefit, diagnosis, prolonged-exposure risk, or recommendation safety. It is integrated as a reproducible evaluated training module; no browser runtime claims are made because this experiment consumes official precomputed visual features rather than raw camera frames.
