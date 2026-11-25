from __future__ import annotations

import argparse
import importlib.util
import json
import math
import multiprocessing as mp
import os
import sys
import tempfile
from multiprocessing.connection import Client, Listener
from pathlib import Path

import numpy as np

from secure_aggregation import generate_keypair, mask_update, validate_masked_payload


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _scale_features(x: np.ndarray) -> np.ndarray:
    scale = np.concatenate([
        np.full(156, math.pi), np.full(3, 3.0), np.full(3, 3.0), np.full(3, math.pi),
        np.full(156, math.pi), np.full(3, 0.5), np.full(3, 0.5), np.full(3, 0.5),
    ])
    return np.clip(x / scale, -3.0, 3.0).astype(np.float64)


def _sequence_split(sequences, labels, subject_mask):
    train_sequences, evaluation_sequences = set(), set()
    for label in sorted(np.unique(labels[subject_mask]).tolist()):
        values = sorted(np.unique(sequences[subject_mask & (labels == label)]).tolist())
        if len(values) == 1:
            train_sequences.update(values)
            continue
        split = max(1, min(len(values) - 1, int(math.ceil(len(values) * 0.6))))
        train_sequences.update(values[:split])
        evaluation_sequences.update(values[split:])
    train = subject_mask & np.isin(sequences, sorted(train_sequences))
    evaluate = subject_mask & np.isin(sequences, sorted(evaluation_sequences))
    if not train.any() or not evaluate.any() or set(sequences[train]) & set(sequences[evaluate]):
        raise RuntimeError("invalid client sequence split")
    return train, evaluate


def _coordinator(expected_clients, authkey, ready_queue, result_queue):
    listener = Listener(("127.0.0.1", 0), authkey=authkey)
    ready_queue.put(listener.address)
    connections, public_keys = {}, {}
    try:
        while len(connections) < expected_clients:
            connection = listener.accept()
            message = connection.recv()
            if set(message) != {"phase", "client_id", "public_key"} or message["phase"] != "register":
                raise RuntimeError("invalid registration")
            client_id = str(message["client_id"])
            if client_id in connections:
                raise RuntimeError("duplicate client")
            connections[client_id] = connection
            public_keys[client_id] = bytes(message["public_key"])
        roster = {client_id: public_keys[client_id] for client_id in sorted(public_keys)}
        for connection in connections.values():
            connection.send({"phase": "roster", "public_keys": roster})

        aggregate, pids, payload_hashes = None, [], []
        for client_id in sorted(connections):
            payload = connections[client_id].recv()
            validate_masked_payload(payload)
            if payload["client_id"] != client_id:
                raise RuntimeError("client/connection mismatch")
            pids.append(int(payload["pid"]))
            payload_hashes.append(sorted(payload))
            update = {name: np.asarray(value, dtype=np.float64) for name, value in payload["masked_update"].items()}
            if aggregate is None:
                aggregate = {name: value.copy() for name, value in update.items()}
            else:
                for name in aggregate:
                    aggregate[name] += update[name]
        result_queue.put({
            "masked_sum": aggregate,
            "independent_processes": len(set(pids)),
            "received_fields": payload_hashes,
            "received_private_keys": False,
            "received_plaintext_updates": False,
        })
    except Exception as exc:
        result_queue.put({"error": repr(exc)})
    finally:
        for connection in connections.values():
            connection.close()
        listener.close()


def _client(client_id, cache_path, initial_model, repo, address, authkey, seed, round_id, local_epochs):
    common = _load_module(f"secure_common_{client_id}", Path(repo) / "machine-learning" / "federated" / "common.py")
    private, public = generate_keypair()
    connection = Client(address, authkey=authkey)
    connection.send({"phase": "register", "client_id": client_id, "public_key": public})
    roster = connection.recv()["public_keys"]
    with np.load(cache_path, allow_pickle=False) as data:
        x_train = np.asarray(data["x_train"], dtype=np.float64)
        y_train = np.asarray(data["y_train"], dtype=np.int64)
    trained = common.local_train(
        initial_model, x_train, y_train, epochs=local_epochs, lr=0.015,
        batch_size=64, seed=seed, class_balance=True,
    )
    update, _, _ = common.clip_update(common.delta(trained, initial_model), 5.0)
    connection.send({
        "phase": "masked_update",
        "client_id": client_id,
        "pid": os.getpid(),
        "samples": int(len(y_train)),
        "masked_update": mask_update(client_id, private, roster, update, round_id=round_id),
    })
    connection.close()


def run(repo: Path, output: Path, local_epochs: int) -> dict:
    behave = _load_module("secure_behave", repo / "machine-learning" / "train_behave_relation.py")
    common = _load_module("secure_common_main", repo / "machine-learning" / "federated" / "common.py")
    config = behave.load_config(repo / "machine-learning" / "datasets" / "behave-relation.json")
    x_raw, y_text, subjects, sequences, _ = behave.load_dataset(config, repo)
    x = _scale_features(x_raw)
    labels = list(config["classes"])
    lookup = {name: index for index, name in enumerate(labels)}
    y = np.asarray([lookup[value] for value in y_text], dtype=np.int64)
    client_ids = sorted(np.unique(subjects).tolist())
    if len(client_ids) != 7:
        raise RuntimeError(f"expected seven BEHAVE participants, found {len(client_ids)}")

    output.mkdir(parents=True, exist_ok=True)
    seed, round_id = 20261125, "behave-secagg-round-1"
    initial = common.init_model(x.shape[1], 64, len(labels), seed)
    evaluation_x, evaluation_y = [], []
    with tempfile.TemporaryDirectory(prefix="healthverse-secagg-") as cache_dir:
        cache_paths = {}
        for client_id in client_ids:
            train, evaluate = _sequence_split(sequences, y_text, subjects == client_id)
            path = Path(cache_dir) / f"{client_id}.npz"
            np.savez_compressed(path, x_train=x[train], y_train=y[train])
            cache_paths[client_id] = path
            evaluation_x.append(x[evaluate])
            evaluation_y.append(y[evaluate])

        context = mp.get_context("spawn")
        ready_queue, result_queue = context.Queue(), context.Queue()
        authkey = os.urandom(32)
        server = context.Process(target=_coordinator, args=(7, authkey, ready_queue, result_queue))
        server.start()
        address = ready_queue.get(timeout=30)
        clients = []
        for index, client_id in enumerate(client_ids):
            process = context.Process(
                target=_client,
                args=(client_id, str(cache_paths[client_id]), initial, str(repo), address,
                      authkey, seed + index, round_id, local_epochs),
            )
            process.start()
            clients.append(process)
        for process in clients:
            process.join(timeout=300)
            if process.is_alive():
                process.terminate()
                process.join()
                raise RuntimeError("client timeout")
            if process.exitcode != 0:
                raise RuntimeError(f"client exited {process.exitcode}")
        result = result_queue.get(timeout=60)
        server.join(timeout=60)
        if server.is_alive():
            server.terminate()
            server.join()
            raise RuntimeError("coordinator timeout")
        if "error" in result:
            raise RuntimeError(result["error"])

        raw_updates = []
        for index, client_id in enumerate(client_ids):
            with np.load(cache_paths[client_id], allow_pickle=False) as data:
                trained = common.local_train(
                    initial, data["x_train"], data["y_train"], epochs=local_epochs,
                    lr=0.015, batch_size=64, seed=seed + index, class_balance=True,
                )
            update, _, _ = common.clip_update(common.delta(trained, initial), 5.0)
            raw_updates.append(update)

    raw_sum = {name: sum(update[name] for update in raw_updates) for name in initial}
    maximum_error = max(float(np.max(np.abs(raw_sum[name] - result["masked_sum"][name]))) for name in initial)
    secure_model, reference_model = common.clone_model(initial), common.clone_model(initial)
    for name in initial:
        secure_model[name] += result["masked_sum"][name] / 7
        reference_model[name] += raw_sum[name] / 7
    evaluation_x = np.vstack(evaluation_x)
    evaluation_y = np.concatenate(evaluation_y)
    secure_prediction = common.predict_proba(secure_model, evaluation_x).argmax(axis=1)
    reference_prediction = common.predict_proba(reference_model, evaluation_x).argmax(axis=1)
    metrics = common.classification_metrics(evaluation_y, secure_prediction, labels)
    parity = bool(np.array_equal(secure_prediction, reference_prediction))
    report = {
        "status": "protocol_passed_utility_below_deployment_gate" if maximum_error <= 1e-10 and parity else "failed",
        "run_type": "single_machine_seven_process_localhost",
        "real_clients": 7,
        "independent_client_processes": result["independent_processes"],
        "local_epochs": local_epochs,
        "key_agreement": "ephemeral X25519",
        "mask_derivation": "HKDF-SHA256 pair masks with opposite signs",
        "coordinator_received_private_keys": result["received_private_keys"],
        "coordinator_received_plaintext_updates": result["received_plaintext_updates"],
        "aggregate_maximum_absolute_error": maximum_error,
        "secure_and_plaintext_predictions_identical": parity,
        "frozen_evaluation": metrics,
        "limitations": [
            "All clients ran as independent processes on one physical machine, not on real remote devices.",
            "Dropout recovery, malicious-client robustness, and transport TLS are not implemented.",
            "Secure aggregation hides individual plaintext updates from this coordinator but does not provide differential privacy for the aggregate model.",
        ],
    }
    (output / "metrics.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--local-epochs", type=int, default=60)
    args = parser.parse_args()
    report = run(args.repo.resolve(), args.output.resolve(), args.local_epochs)
    print(json.dumps({"status": report["status"], "output": str(args.output.resolve())}))


if __name__ == "__main__":
    mp.freeze_support()
    main()
