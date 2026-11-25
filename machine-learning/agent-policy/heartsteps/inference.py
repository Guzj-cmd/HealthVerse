from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import joblib
import numpy as np
import pandas as pd


ALLOWED_RELATIONS = {"chair_sit", "seated_contact"}
ALLOWED_OUTPUTS = {"no_action", "offer_activity_suggestion", "ask_confirm"}
TRANSIT_ACTIVITIES = {"IN_VEHICLE", "ON_BICYCLE", "AUGMENTED_VEHICLE"}
FEATURE_MAP = {
    "decision_slot": "decision_slot",
    "study_day": "study_day",
    "jawbone_steps_previous_30m": "jbsteps30pre.zero",
    "jawbone_steps_previous_60m": "jbsteps60pre.zero",
    "google_fit_steps_previous_30m": "gfsteps30pre",
    "google_fit_steps_previous_60m": "gfsteps60pre",
    "temperature_c": "dec.temperature",
    "wind_speed_mph": "dec.windspeed",
    "precipitation_chance": "dec.precipitation.chance",
    "snow_mm": "dec.snow",
    "past_suggestions_5": "past_suggestions_5",
    "past_suggestions_20": "past_suggestions_20",
    "recognized_activity": "recognized.activity",
    "location_category": "dec.location.category",
    "weather_condition": "dec.weather.condition",
}


def _decision(action: str, reason: str, *, benefit: float | None = None) -> dict:
    result = {
        "immutable_action": action,
        "policy_state": reason,
        "scope": "non_medical_activity_suggestion_only",
        "evidence_codes": [],
    }
    if benefit is not None:
        result["predicted_log_step_benefit"] = float(benefit)
    return result


def _finite_number(context: dict, key: str) -> float:
    value = context.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(key)
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(key)
    return value


def decide(bundle: dict, context: dict) -> dict:
    """Apply the frozen HeartSteps component behind explicit safety evidence gates.

    The randomized-trial evaluation covers the activity-suggestion component.
    The upstream visual relation gate is a conservative integration boundary and
    was not jointly randomized with HeartSteps.
    """
    if context.get("source_model_status") != "passed":
        return _decision("ask_confirm", "source_model_not_passed")
    relation = context.get("predicted_relation")
    if relation not in ALLOWED_RELATIONS:
        return _decision("no_action", "relation_not_eligible")
    if context.get("user_available") is not True:
        return _decision("no_action", "user_unavailable")
    activity = context.get("recognized_activity")
    if activity in TRANSIT_ACTIVITIES:
        return _decision("no_action", "unsafe_transit_context")
    if not isinstance(activity, str) or not activity:
        return _decision("ask_confirm", "context_missing")
    if not isinstance(context.get("location_category"), str) or not context["location_category"]:
        return _decision("ask_confirm", "context_missing")
    if not isinstance(context.get("weather_condition"), str) or not context["weather_condition"]:
        return _decision("ask_confirm", "context_missing")
    try:
        numeric = {
            key: _finite_number(context, key)
            for key in FEATURE_MAP
            if key not in {"recognized_activity", "location_category", "weather_condition"}
        }
    except ValueError:
        return _decision("ask_confirm", "context_invalid")
    if not 0 <= numeric["decision_slot"] <= 4 or not 0 <= numeric["study_day"] <= 41:
        return _decision("ask_confirm", "context_out_of_range")
    if not 0 <= numeric["precipitation_chance"] <= 100:
        return _decision("ask_confirm", "context_out_of_range")
    if not 0 <= numeric["past_suggestions_5"] <= 5 or not 0 <= numeric["past_suggestions_20"] <= 20:
        return _decision("ask_confirm", "context_out_of_range")
    nonnegative = [
        "jawbone_steps_previous_30m",
        "jawbone_steps_previous_60m",
        "google_fit_steps_previous_30m",
        "google_fit_steps_previous_60m",
        "wind_speed_mph",
        "snow_mm",
    ]
    if any(numeric[key] < 0 for key in nonnegative):
        return _decision("ask_confirm", "context_out_of_range")

    row = {target: context[source] for source, target in FEATURE_MAP.items()}
    frame = pd.DataFrame([row], columns=bundle["features"])
    transformed = bundle["preprocessor"].transform(frame)
    mu0 = float(np.asarray(bundle["models"][0].predict(transformed))[0])
    mu1 = float(np.asarray(bundle["models"][1].predict(transformed))[0])
    benefit = mu1 - mu0
    action = "offer_activity_suggestion" if benefit > float(bundle["threshold"]) else "no_action"
    if action not in ALLOWED_OUTPUTS:
        return _decision("ask_confirm", "model_action_out_of_contract")
    result = _decision(action, "learned_policy", benefit=benefit)
    result["evidence_codes"] = [
        "passed_relation_model",
        "eligible_seated_relation",
        "user_available",
        "heartsteps_context",
    ]
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--context", type=Path, required=True)
    args = parser.parse_args()
    bundle = joblib.load(args.model)
    context = json.loads(args.context.read_text(encoding="utf-8"))
    print(json.dumps(decide(bundle, context), ensure_ascii=False))


if __name__ == "__main__":
    main()
