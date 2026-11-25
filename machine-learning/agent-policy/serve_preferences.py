"""Small local HTTP API for UI preference collection; no external service required."""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from preference_store import PreferenceStore, eligibility


def create_handler(store: PreferenceStore, config: dict):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, body: dict) -> None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _body(self) -> dict:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 1_000_000:
                raise ValueError("request body size is invalid")
            return json.loads(self.rfile.read(length).decode("utf-8"))

        def do_GET(self) -> None:  # noqa: N802
            if self.path != "/api/rlhf/status":
                self._send(404, {"error": "not_found"}); return
            counts = store.counts()
            state, blockers = eligibility(counts, config["feedback_policy"])
            self._send(200, {"state": state, "counts": counts, "blockers": blockers})

        def do_POST(self) -> None:  # noqa: N802
            try:
                payload = self._body()
                if self.path == "/api/preferences":
                    stored = store.record(payload["event"], payload["participant_token"], payload["session_token"])
                    self._send(201, {"stored": True, "event_id": stored["event_id"]})
                elif self.path == "/api/preferences/withdraw":
                    removed = store.withdraw(payload["participant_token"])
                    self._send(200, {"withdrawn": True, "events_removed": removed})
                else:
                    self._send(404, {"error": "not_found"})
            except (KeyError, ValueError, json.JSONDecodeError) as exc:
                self._send(400, {"error": "invalid_preference", "detail": str(exc)})
            except Exception as exc:  # duplicate event IDs and storage errors
                self._send(409, {"error": "not_stored", "detail": str(exc)})

        def log_message(self, format: str, *args) -> None:
            return

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--jsonl", default="data/preferences.jsonl")
    parser.add_argument("--sqlite", default="data/preferences.sqlite3")
    parser.add_argument("--config", default="config.json")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    store = PreferenceStore(Path(args.jsonl), Path(args.sqlite))
    server = ThreadingHTTPServer((args.host, args.port), create_handler(store, config))
    print(json.dumps({"listening": f"http://{args.host}:{args.port}", "raw_media_retained": False}, ensure_ascii=False))
    server.serve_forever()


if __name__ == "__main__":
    main()
