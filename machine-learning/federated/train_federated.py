from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from common import (aggregate, classification_metrics, clip_update, delta, init_model, load_jsonl,
                    local_train, model_to_json, predict_proba, split_subjects)


def evaluate(model, data, subjects):
    mask = np.isin(data.subjects, subjects)
    pred = predict_proba(model, data.x[mask]).argmax(axis=1)
    return classification_metrics(data.y[mask], pred, data.labels)


def main() -> int:
    parser = argparse.ArgumentParser(description="Real-data FedAvg simulation for HealthVerse posture classification")
    parser.add_argument("--data", required=True)
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
    data = load_jsonl(args.data)
    split = split_subjects(data.subjects, cfg["seed"], cfg["split"]["train_subjects"], cfg["split"]["validation_subjects"])
    model = init_model(data.x.shape[1], cfg["model"]["hidden_dim"], len(data.labels), cfg["seed"])
    rows, participation, total_bytes = [], [], 0

    train_clients = split["train"]
    for round_no in range(1, cfg["federated"]["rounds"] + 1):
        updates = []
        for client_index, subject in enumerate(train_clients):
            mask = data.subjects == subject
            trained = local_train(model, data.x[mask], data.y[mask], epochs=cfg["federated"]["local_epochs"],
                                  lr=cfg["federated"]["learning_rate"], batch_size=cfg["federated"]["batch_size"],
                                  seed=cfg["seed"] + round_no * 100 + client_index,
                                  class_balance=cfg["federated"].get("class_balance", False))
            update, raw_norm, clip_factor = clip_update(delta(trained, model), cfg["privacy"]["update_clip_norm"])
            update_bytes = sum(value.nbytes for value in update.values())
            total_bytes += update_bytes
            updates.append((int(mask.sum()), update))
            participation.append([round_no, subject, int(mask.sum()), raw_norm, clip_factor, update_bytes])
        model = aggregate(model, updates, noise_std=cfg["privacy"]["gaussian_noise_std"], seed=cfg["seed"] + round_no)
        train_result = evaluate(model, data, split["train"])
        val_result = evaluate(model, data, split["validation"])
        rows.append([round_no, train_result["accuracy"], train_result["macro_f1"], val_result["accuracy"], val_result["macro_f1"], total_bytes])

    test_result = evaluate(model, data, split["test"])
    client_results = {}
    for subject in split["test"]:
        client_results[subject] = evaluate(model, data, [subject])
    worst_client = min(client_results, key=lambda key: client_results[key]["macro_f1"])

    central = init_model(data.x.shape[1], cfg["model"]["hidden_dim"], len(data.labels), cfg["seed"])
    train_mask = np.isin(data.subjects, split["train"])
    central = local_train(central, data.x[train_mask], data.y[train_mask],
                          epochs=cfg["baseline"]["epochs"], lr=cfg["baseline"]["learning_rate"],
                          batch_size=cfg["baseline"]["batch_size"], seed=cfg["seed"],
                          class_balance=cfg["baseline"].get("class_balance", False))
    central_test = evaluate(central, data, split["test"])

    thresholds = cfg["thresholds"]
    failures = []
    if test_result["accuracy"] < thresholds["accuracy"]: failures.append("accuracy")
    if test_result["macro_f1"] < thresholds["macro_f1"]: failures.append("macro_f1")
    low = [label for label, value in test_result["per_class_recall"].items() if value < thresholds["minimum_class_recall"]]
    if low: failures.append("class_recall:" + ",".join(low))
    if len(split["test"]) < thresholds["minimum_test_subjects"]: failures.append("test_subject_count")
    status = "passed" if not failures else "failed"
    report = {
        "status": status, "failed_thresholds": failures, "run_type": "local_federated_test",
        "claim_scope": "single-machine multi-client FedAvg simulation; not a real multi-device deployment",
        "evaluation_scope": cfg.get("evaluation_scope", "confirmatory_if_test_not_previously_consulted"),
        "dataset": Path(args.data).name, "labels": data.labels, "split_subjects": split,
        "federated_test": test_result, "centralized_baseline_test": central_test,
        "federated_minus_central_macro_f1": test_result["macro_f1"] - central_test["macro_f1"],
        "per_test_client": client_results,
        "worst_test_client": {"subject": worst_client, **client_results[worst_client]},
        "communication_bytes_uploaded": total_bytes,
        "privacy": {
            "raw_samples_uploaded": False, "update_clip_norm": cfg["privacy"]["update_clip_norm"],
            "gaussian_noise_std": cfg["privacy"]["gaussian_noise_std"],
            "differential_privacy_epsilon": "not_applicable" if cfg["privacy"]["gaussian_noise_std"] == 0 else "not_accounted",
            "secure_aggregation": False,
        },
        "thresholds": thresholds, "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (out / "metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "model.json").write_text(json.dumps({"labels": data.labels, "parameters": model_to_json(model)}), encoding="utf-8")
    with (out / "round_history.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle); writer.writerow(["round", "train_accuracy", "train_macro_f1", "validation_accuracy", "validation_macro_f1", "cumulative_upload_bytes"]); writer.writerows(rows)
    with (out / "client_participation.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle); writer.writerow(["round", "client_subject", "samples", "raw_update_norm", "clip_factor", "upload_bytes"]); writer.writerows(participation)
    recalls = "\n".join(f"- {name}: {value:.4f}" for name, value in test_result["per_class_recall"].items())
    (out / "model_card.md").write_text(f"""# HealthVerse Federated Posture Model\n\n- Status: **{status}**\n- Run type: `local_federated_test`\n- Evaluation scope: `{cfg.get('evaluation_scope', 'confirmatory_if_test_not_previously_consulted')}`\n- Dataset: `{Path(args.data).name}` (real MultiPosture participant landmarks)\n- Split: unseen participants; train {len(split['train'])}, validation {len(split['validation'])}, test {len(split['test'])}\n- FedAvg test accuracy: {test_result['accuracy']:.4f}\n- FedAvg test Macro-F1: {test_result['macro_f1']:.4f}\n- Centralized baseline Macro-F1: {central_test['macro_f1']:.4f}\n- Uploaded parameter bytes: {total_bytes}\n\n## Per-class recall\n\n{recalls}\n\n## Privacy and claim boundary\n\nRaw landmarks never enter the aggregator in this simulation; only clipped parameter updates are averaged. Secure aggregation is not implemented, differential privacy is disabled, and epsilon is therefore not applicable. This run simulates subject clients on one computer and must not be described as a real multi-device deployment.\n""", encoding="utf-8")
    print(json.dumps({"status": status, "metrics": str(out / "metrics.json")}, ensure_ascii=False))
    return 0 if status == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
