# Charades relation head model card

## Intended use

Research-only auxiliary recognition of seven observable human-environment
relations in indoor videos. It is not a medical model, ergonomic diagnosis,
or direct advice generator.

## Real-data protocol

- Source: official Charades v1 RGB two-stream fc7 features.
- Official train: 7985 videos / 214 subjects.
- Official test: 1863 videos / 53 subjects.
- Subject overlap: 0.
- Hyperparameters and thresholds were selected using grouped folds inside the
  official train split. The official test split was evaluated once.

## Results

- Gate: **REJECTED**
- Official-test macro mAP: 0.363442
- Official-test macro F1: 0.456242
- Official-test macro ECE: 0.133941

| Relation | AP | Recall | Positive videos |
|---|---:|---:|---:|
| chair_sit | 0.4456 | 0.3671 | 365 |
| table_relation | 0.4081 | 0.4865 | 222 |
| laptop_interaction | 0.2233 | 0.4101 | 139 |
| couch_contact | 0.4008 | 0.4545 | 209 |
| floor_contact | 0.2383 | 0.3688 | 160 |
| bed_contact | 0.3214 | 0.4862 | 181 |
| sit_stand_transition | 0.5065 | 0.4015 | 538 |

## Gate failures

- chair_sit recall 0.367123 below minimum
- table_relation recall 0.486486 below minimum
- laptop_interaction recall 0.410072 below minimum
- couch_contact recall 0.454545 below minimum
- floor_contact recall 0.368750 below minimum
- bed_contact recall 0.486188 below minimum
- sit_stand_transition recall 0.401487 below minimum

## License and privacy

The source archive is not redistributed. The AllenAI license permits
non-commercial research but forbids third-party redistribution of the data.
The local model artifact and video-level predictions remain Git-ignored by
default pending a separate derived-artifact license decision.
