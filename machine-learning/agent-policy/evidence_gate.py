from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import joblib
import numpy as np


ALLOWED_RELATIONS = {"seated_contact", "table_lean", "monitor_interaction"}
ALLOWED_ACTIONS = {"no_action", "ask_confirm"}


def _fallback(reason: str, confidence: float = 0.0) -> dict:
    return {
        "immutable_action": "ask_confirm",
        "confidence": float(confidence),
        "policy_state": "fallback",
        "evidence_codes": [reason],
        "scope": "safety_gate_only",
    }


def _classes(model) -> list[str]:
    classifier = getattr(model, "named_steps", {}).get("classifier", model)
    return [str(value) for value in classifier.classes_]


def decide(model, context: dict, minimum_confidence: float = 0.70) -> dict:
    """Return a frozen safety-gate action from upstream structured evidence.

    This head cannot emit environment-changing or health-advice actions. Invalid,
    unsupported, or low-confidence evidence always requests confirmation.
    """
    relation = context.get("predicted_relation")
    object_name = context.get("object")
    consistency = context.get("frame_consistency")
    if context.get("source_model_status") != "passed":
        return _fallback("source_model_not_passed")
    if relation not in ALLOWED_RELATIONS:
        return _fallback("relation_out_of_contract")
    if not isinstance(object_name, str) or not object_name.strip():
        return _fallback("object_missing")
    if not isinstance(consistency, (int, float)) or not math.isfinite(float(consistency)):
        return _fallback("frame_consistency_invalid")
    if not 0.0 <= float(consistency) <= 1.0:
        return _fallback("frame_consistency_invalid")

    x = np.asarray([[relation, object_name, float(consistency)]], dtype=object)
    probability = np.asarray(model.predict_proba(x)[0], dtype=float)
    classes = _classes(model)
    index = int(np.argmax(probability))
    action, confidence = classes[index], float(probability[index])
    if action not in ALLOWED_ACTIONS:
        return _fallback("learned_action_out_of_contract")
    if confidence < minimum_confidence:
        decision = _fallback("learned_confidence_below_threshold", confidence)
        decision["policy_state"] = "low_confidence_fallback"
        return decision
    return {
        "immutable_action": action,
        "confidence": confidence,
        "policy_state": "learned_gate",
        "evidence_codes": ["predicted_relation", "object", "frame_consistency"],
        "scope": "safety_gate_only",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--minimum-confidence", type=float, default=0.70)
    args = parser.parse_args()
    context = json.loads(args.context.read_text(encoding="utf-8"))
    print(json.dumps(decide(joblib.load(args.model), context, args.minimum_confidence), ensure_ascii=False))


if __name__ == "__main__":
    main()
