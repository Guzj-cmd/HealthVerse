from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import secrets
import ssl
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np

from common import aggregate, clip_update, init_model, model_from_json, model_to_json, sign_body


class State:
    def __init__(self, secret: str, input_dim: int, hidden_dim: int, classes: int, min_clients: int, clip_norm: float):
        self.secret, self.min_clients, self.clip_norm = secret, min_clients, clip_norm
        self.model = init_model(input_dim, hidden_dim, classes, seed=20261125)
        self.round = 1
        self.clients: dict[str, dict] = {}
        self.pending: dict[str, tuple[int, dict[str, np.ndarray], str]] = {}
        self.completed_rounds: list[dict] = []
        self.lock = threading.Lock()

    def token(self, client_id: str) -> str:
        return hmac.new(self.secret.encode(), f"{self.round}:{client_id}".encode(), hashlib.sha256).hexdigest()

    def status(self) -> dict:
        fingerprints = {row["fingerprint"] for row in self.clients.values()}
        completed_multi = any(item["distinct_device_fingerprints"] >= 2 for item in self.completed_rounds)
        return {
            "round": self.round, "registered_clients": len(self.clients), "distinct_device_fingerprints": len(fingerprints),
            "pending_updates": len(self.pending), "completed_rounds": self.completed_rounds,
            "run_type": "multi_device_federated_run" if completed_multi else "local_federated_test",
            "raw_samples_accepted": False, "secure_aggregation": False,
        }


def handler_factory(state: State):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, value: dict):
            body = json.dumps(value, ensure_ascii=False).encode()
            self.send_response(status); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

        def _body(self):
            raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            signature = self.headers.get("X-HV-Signature", "")
            if not hmac.compare_digest(signature, sign_body(state.secret, raw)):
                raise PermissionError("invalid HMAC signature")
            value = json.loads(raw or b"{}")
            forbidden = {"landmarks", "samples", "features", "x", "y"} & set(value)
            if forbidden:
                raise ValueError("raw training data is forbidden at the coordinator")
            return value

        def do_GET(self):
            if self.path == "/status": return self._send(200, state.status())
            if self.path.startswith("/model?"):
                client_id = self.path.split("client_id=", 1)[-1]
                if client_id not in state.clients: return self._send(403, {"error": "unregistered client"})
                return self._send(200, {"round": state.round, "round_token": state.token(client_id), "parameters": model_to_json(state.model)})
            return self._send(404, {"error": "not found"})

        def do_POST(self):
            try: value = self._body()
            except (PermissionError, ValueError, json.JSONDecodeError) as exc: return self._send(403, {"error": str(exc)})
            if self.path == "/register":
                fingerprint = str(value.get("device_fingerprint", ""))
                if len(fingerprint) != 64: return self._send(400, {"error": "invalid anonymous fingerprint"})
                client_id = secrets.token_hex(16)
                state.clients[client_id] = {"fingerprint": fingerprint, "active": True}
                return self._send(200, {"client_id": client_id, "round": state.round})
            if self.path == "/withdraw":
                client_id = str(value.get("client_id", ""))
                state.clients.pop(client_id, None); state.pending.pop(client_id, None)
                return self._send(200, {"withdrawn": True, "server_retains_raw_data": False})
            if self.path == "/update":
                client_id = str(value.get("client_id", ""))
                if client_id not in state.clients: return self._send(403, {"error": "unregistered client"})
                if value.get("round_token") != state.token(client_id): return self._send(403, {"error": "invalid or stale round token"})
                update = model_from_json(value["update"])
                if set(update) != set(state.model) or any(update[key].shape != state.model[key].shape for key in state.model): return self._send(400, {"error": "parameter schema mismatch"})
                clipped, raw_norm, factor = clip_update(update, state.clip_norm)
                with state.lock:
                    state.pending[client_id] = (int(value["sample_count"]), clipped, state.clients[client_id]["fingerprint"])
                    aggregated = False
                    if len(state.pending) >= state.min_clients:
                        used = list(state.pending.values())
                        state.model = aggregate(state.model, [(count, delta) for count, delta, _ in used], seed=state.round)
                        state.completed_rounds.append({"round": state.round, "clients": len(used), "distinct_device_fingerprints": len({fp for _, _, fp in used})})
                        state.pending.clear(); state.round += 1; aggregated = True
                return self._send(200, {"accepted": True, "aggregated": aggregated, "raw_update_norm": raw_norm, "server_clip_factor": factor, **state.status()})
            return self._send(404, {"error": "not found"})

        def log_message(self, format, *args):
            return
    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description="HealthVerse HMAC-authenticated FedAvg coordinator")
    parser.add_argument("--host", default="127.0.0.1"); parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--secret", required=True); parser.add_argument("--input-dim", type=int, default=99)
    parser.add_argument("--hidden-dim", type=int, default=64); parser.add_argument("--classes", type=int, default=5)
    parser.add_argument("--min-clients", type=int, default=2); parser.add_argument("--clip-norm", type=float, default=5.0)
    parser.add_argument("--tls-cert"); parser.add_argument("--tls-key")
    args = parser.parse_args()
    state = State(args.secret, args.input_dim, args.hidden_dim, args.classes, args.min_clients, args.clip_norm)
    server = ThreadingHTTPServer((args.host, args.port), handler_factory(state))
    if args.tls_cert and args.tls_key:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); context.load_cert_chain(args.tls_cert, args.tls_key)
        server.socket = context.wrap_socket(server.socket, server_side=True)
    print(json.dumps({"listening": f"{args.host}:{args.port}", "tls": bool(args.tls_cert), "run_type": "local_federated_test"}))
    server.serve_forever()
    return 0


if __name__ == "__main__": raise SystemExit(main())
