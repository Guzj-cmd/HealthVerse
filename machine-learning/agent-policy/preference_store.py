"""Consent-gated local persistence for real pairwise preference feedback."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sqlite3
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

ACTIONS = {"no_action", "ask_confirm", "raise_monitor", "reposition_object", "take_break"}
CHOICES = {"A", "B", "tie", "neither"}
HASH_RE = re.compile(r"^[a-f0-9]{64}$")
RAW_MEDIA_KEYS = {"image", "frame", "video", "audio", "raw_media", "raw_bytes", "base64"}


def anonymize_identifier(raw_identifier: str, secret: str) -> str:
    if not raw_identifier or not secret:
        raise ValueError("identifier and HEALTHVERSE_FEEDBACK_SALT are required")
    return hmac.new(secret.encode("utf-8"), raw_identifier.encode("utf-8"), hashlib.sha256).hexdigest()


def _contains_raw_media(value: Any) -> bool:
    if isinstance(value, dict):
        return any(str(key).lower() in RAW_MEDIA_KEYS or _contains_raw_media(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_raw_media(item) for item in value)
    return False


def validate_event(event: dict[str, Any]) -> None:
    required = {
        "schema_version", "event_id", "recorded_at", "anonymous_participant_id",
        "anonymous_session_id", "consent", "context", "candidate_a", "candidate_b", "preference",
    }
    missing = required - set(event)
    if missing:
        raise ValueError(f"missing fields: {sorted(missing)}")
    if event["schema_version"] != "1.0.0":
        raise ValueError("unsupported schema_version")
    if not HASH_RE.fullmatch(str(event["anonymous_participant_id"])) or not HASH_RE.fullmatch(str(event["anonymous_session_id"])):
        raise ValueError("participant/session identifiers must be HMAC-SHA256 hashes")
    consent = event["consent"]
    if consent != {"granted": True, "notice_version": "2026-11-25", "raw_media_retained": False, "may_withdraw": True}:
        raise ValueError("current explicit consent is required and raw media retention must be false")
    if _contains_raw_media(event):
        raise ValueError("raw image/video/audio fields are not accepted")
    context = event["context"]
    if context.get("pose_class") not in {"TUP", "TLB", "TLF", "TLR", "TLL"}:
        raise ValueError("invalid pose_class")
    probs = context.get("pose_probs", {})
    if set(probs) != {"TUP", "TLB", "TLF", "TLR", "TLL"} or any(not 0 <= float(v) <= 1 for v in probs.values()):
        raise ValueError("pose_probs must contain five probabilities")
    if abs(sum(float(v) for v in probs.values()) - 1.0) > 0.05:
        raise ValueError("pose_probs must sum to approximately one")
    action_a, action_b = event["candidate_a"].get("action"), event["candidate_b"].get("action")
    if action_a not in ACTIONS or action_b not in ACTIONS or action_a == action_b:
        raise ValueError("candidates must contain two distinct supported actions")
    preference = event["preference"]
    if preference.get("choice") not in CHOICES:
        raise ValueError("invalid pairwise choice")
    if int(preference.get("latency_ms", -1)) < 0:
        raise ValueError("latency_ms must be non-negative")


class PreferenceStore:
    def __init__(self, jsonl_path: Path, sqlite_path: Path, secret: str | None = None):
        self.jsonl_path = Path(jsonl_path)
        self.sqlite_path = Path(sqlite_path)
        self.secret = secret or os.environ.get("HEALTHVERSE_FEEDBACK_SALT", "")
        if not self.secret:
            raise ValueError("set HEALTHVERSE_FEEDBACK_SALT before collecting feedback")
        self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.sqlite_path) as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS preferences (
                    event_id TEXT PRIMARY KEY,
                    participant_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    choice TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
            """)

    def record(self, event: dict[str, Any], participant_token: str, session_token: str) -> dict[str, Any]:
        stored = dict(event)
        stored["anonymous_participant_id"] = anonymize_identifier(participant_token, self.secret)
        stored["anonymous_session_id"] = anonymize_identifier(session_token, self.secret)
        validate_event(stored)
        payload = json.dumps(stored, ensure_ascii=False, separators=(",", ":"))
        with sqlite3.connect(self.sqlite_path) as connection:
            connection.execute(
                "INSERT INTO preferences(event_id,participant_id,session_id,choice,recorded_at,payload_json) VALUES(?,?,?,?,?,?)",
                (stored["event_id"], stored["anonymous_participant_id"], stored["anonymous_session_id"], stored["preference"]["choice"], stored["recorded_at"], payload),
            )
        with self.jsonl_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(payload + "\n")
        return stored

    def withdraw(self, participant_token: str) -> int:
        participant_id = anonymize_identifier(participant_token, self.secret)
        with sqlite3.connect(self.sqlite_path) as connection:
            count = connection.execute("SELECT COUNT(*) FROM preferences WHERE participant_id=?", (participant_id,)).fetchone()[0]
            connection.execute("DELETE FROM preferences WHERE participant_id=?", (participant_id,))
        if self.jsonl_path.exists():
            retained: list[str] = []
            for line in self.jsonl_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("anonymous_participant_id") != participant_id:
                    retained.append(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", delete=False, dir=self.jsonl_path.parent) as handle:
                if retained:
                    handle.write("\n".join(retained) + "\n")
                temporary = Path(handle.name)
            temporary.replace(self.jsonl_path)
        return int(count)

    def counts(self) -> dict[str, Any]:
        with sqlite3.connect(self.sqlite_path) as connection:
            rows = connection.execute("SELECT participant_id,session_id,choice,payload_json FROM preferences").fetchall()
        choices = Counter(row[2] for row in rows)
        actions = Counter()
        for *_, payload in rows:
            event = json.loads(payload)
            actions.update([event["candidate_a"]["action"], event["candidate_b"]["action"]])
        return {
            "events": len(rows),
            "decisive_preferences": choices["A"] + choices["B"],
            "participants": len({row[0] for row in rows}),
            "sessions": len({row[1] for row in rows}),
            "choices": dict(choices),
            "action_exposures": dict(actions),
        }


def eligibility(counts: dict[str, Any], policy_config: dict[str, Any]) -> tuple[str, list[str]]:
    if counts["events"] == 0:
        return "untrained", ["no_real_preference_events"]
    failures: list[str] = []
    checks = {
        "minimum_decisive_preferences": counts["decisive_preferences"],
        "minimum_participants": counts["participants"],
        "minimum_sessions": counts["sessions"],
    }
    for name, observed in checks.items():
        if observed < int(policy_config[name]):
            failures.append(f"{name}:{observed}/{policy_config[name]}")
    minimum_action = int(policy_config["minimum_preferences_per_action"])
    for action in ACTIONS:
        observed = int(counts["action_exposures"].get(action, 0))
        if observed < minimum_action:
            failures.append(f"action_exposure:{action}:{observed}/{minimum_action}")
    return ("eligible" if not failures else "collecting"), failures
