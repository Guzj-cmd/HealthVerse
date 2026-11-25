from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request

from common import clip_update, delta, device_fingerprint, load_jsonl, local_train, model_from_json, model_to_json, sign_body


def post(base: str, path: str, secret: str, value: dict) -> dict:
    body = json.dumps(value, separators=(",", ":")).encode()
    request = urllib.request.Request(base + path, data=body, method="POST", headers={"Content-Type": "application/json", "X-HV-Signature": sign_body(secret, body)})
    with urllib.request.urlopen(request) as response: return json.load(response)


def get(base: str, path: str) -> dict:
    with urllib.request.urlopen(base + path) as response: return json.load(response)


def main() -> int:
    parser = argparse.ArgumentParser(description="HealthVerse federated client; landmarks remain local")
    parser.add_argument("--server", default="http://127.0.0.1:8787"); parser.add_argument("--secret", required=True)
    parser.add_argument("--data"); parser.add_argument("--subject-id"); parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--learning-rate", type=float, default=0.025); parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--clip-norm", type=float, default=5.0); parser.add_argument("--withdraw-client-id")
    args = parser.parse_args()
    if args.withdraw_client_id:
        print(json.dumps(post(args.server, "/withdraw", args.secret, {"client_id": args.withdraw_client_id}), ensure_ascii=False)); return 0
    if not args.data or not args.subject_id: parser.error("--data and --subject-id are required unless withdrawing")
    data = load_jsonl(args.data); mask = data.subjects == args.subject_id
    if not mask.any(): raise ValueError(f"no local rows for {args.subject_id}")
    registration = post(args.server, "/register", args.secret, {"device_fingerprint": device_fingerprint(args.secret)})
    client_id = registration["client_id"]
    payload = get(args.server, "/model?client_id=" + urllib.parse.quote(client_id))
    model = model_from_json(payload["parameters"])
    trained = local_train(model, data.x[mask], data.y[mask], epochs=args.epochs, lr=args.learning_rate,
                          batch_size=args.batch_size, seed=payload["round"], class_balance=True)
    update, raw_norm, factor = clip_update(delta(trained, model), args.clip_norm)
    response = post(args.server, "/update", args.secret, {
        "client_id": client_id, "round_token": payload["round_token"], "sample_count": int(mask.sum()),
        "update": model_to_json(update),
    })
    print(json.dumps({"client_id": client_id, "local_subject": args.subject_id, "raw_data_uploaded": False,
                      "client_raw_update_norm": raw_norm, "client_clip_factor": factor, "server": response}, ensure_ascii=False))
    return 0


if __name__ == "__main__": raise SystemExit(main())
