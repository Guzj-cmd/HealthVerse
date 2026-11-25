from __future__ import annotations

import hashlib
from collections.abc import Mapping

import numpy as np
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


def generate_keypair() -> tuple[X25519PrivateKey, bytes]:
    private = X25519PrivateKey.generate()
    public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return private, public


def pair_mask(private_key: X25519PrivateKey, peer_public: bytes, *, pair_id: str,
              parameter: str, round_id: str, shape: tuple[int, ...]) -> np.ndarray:
    """Derive the same deterministic mask at both ends of one client pair."""
    shared = private_key.exchange(X25519PublicKey.from_public_bytes(peer_public))
    seed_bytes = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=round_id.encode("utf-8"),
        info=f"healthverse-secagg|{pair_id}|{parameter}".encode("utf-8"),
    ).derive(shared)
    seed = int.from_bytes(seed_bytes[:16], "big")
    return np.random.default_rng(seed).standard_normal(shape)


def mask_update(client_id: str, private_key: X25519PrivateKey, roster: Mapping[str, bytes],
                update: Mapping[str, np.ndarray], *, round_id: str) -> dict[str, np.ndarray]:
    masked = {name: np.asarray(value, dtype=np.float64).copy() for name, value in update.items()}
    for peer_id in sorted(roster):
        if peer_id == client_id:
            continue
        pair_id = "|".join(sorted((client_id, peer_id)))
        sign = 1.0 if client_id < peer_id else -1.0
        for name, value in masked.items():
            value += sign * pair_mask(
                private_key,
                roster[peer_id],
                pair_id=pair_id,
                parameter=name,
                round_id=round_id,
                shape=value.shape,
            )
    return masked


def aggregate_masked_updates(updates: list[Mapping[str, np.ndarray]]) -> dict[str, np.ndarray]:
    if not updates:
        raise ValueError("at least one masked update is required")
    names = set(updates[0])
    if any(set(update) != names for update in updates):
        raise ValueError("all updates must contain the same parameters")
    return {
        name: np.sum([np.asarray(update[name], dtype=np.float64) for update in updates], axis=0)
        for name in sorted(names)
    }


def payload_fingerprint(payload: Mapping) -> str:
    """Audit payload structure without logging private tensors or key material."""
    fields = "|".join(sorted(str(key) for key in payload))
    return hashlib.sha256(fields.encode("utf-8")).hexdigest()


def validate_masked_payload(payload: Mapping) -> None:
    required = {"phase", "client_id", "pid", "samples", "masked_update"}
    if set(payload) != required or payload.get("phase") != "masked_update":
        raise ValueError("invalid masked-update payload")
    forbidden = {"private_key", "plaintext_update", "raw_update"}
    if forbidden & set(payload):
        raise ValueError("payload exposes private aggregation material")
