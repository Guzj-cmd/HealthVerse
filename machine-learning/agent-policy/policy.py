"""Runtime policy for a preference-trained reward model.

No rule or synthetic preference labels are created here. Until a reward model
passes held-out gates, the runtime remains conservative and asks the user.
Safety constraints are applied after scoring and are never counted as reward
model accuracy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

ACTIONS = ("no_action", "ask_confirm", "raise_monitor", "reposition_object", "take_break")
MUTATING_ACTIONS = {"raise_monitor", "reposition_object", "take_break"}
VALID_STATES = {"untrained", "collecting", "eligible", "trained", "passed"}


@dataclass(frozen=True)
class Decision:
    action: str
    rationale_codes: tuple[str, ...]
    reward_probability: float | None
    policy_state: str


def constraint_violations(action: str, constraints: Mapping[str, bool]) -> list[str]:
    violations: list[str] = []
    if action == "raise_monitor" and constraints.get("lock_monitor", False):
        violations.append("lock_monitor")
    if action == "reposition_object" and constraints.get("keep_handwriting_zone", False):
        violations.append("keep_handwriting_zone")
    if action == "take_break" and constraints.get("suppress_break", False):
        violations.append("suppress_break")
    if action in MUTATING_ACTIONS and constraints.get("require_confirmation", False):
        violations.append("require_confirmation")
    return violations


def apply_safety_constraints(decision: Decision, constraints: Mapping[str, bool]) -> Decision:
    violations = constraint_violations(decision.action, constraints)
    if not violations:
        return decision
    if violations == ["suppress_break"]:
        return Decision("no_action", decision.rationale_codes + ("constraint:suppress_break",), decision.reward_probability, decision.policy_state)
    return Decision(
        "ask_confirm",
        decision.rationale_codes + tuple(f"constraint:{v}" for v in violations),
        decision.reward_probability,
        decision.policy_state,
    )


def conservative_select(
    policy_state: str,
    scored_candidates: Sequence[tuple[str, float]],
    constraints: Mapping[str, bool],
    minimum_probability: float = 0.70,
) -> Decision:
    """Select only a supported high-confidence action; otherwise request confirmation.

    Scores must come from the passed reward model and represent the probability
    that a candidate is preferred to the baseline in the current context.
    """
    if policy_state not in VALID_STATES:
        raise ValueError(f"unknown policy state: {policy_state}")
    if policy_state != "passed" or not scored_candidates:
        return Decision("ask_confirm", (f"rlhf_state:{policy_state}",), None, policy_state)
    for action, _ in scored_candidates:
        if action not in ACTIONS:
            raise ValueError(f"unsupported action: {action}")
    action, probability = max(scored_candidates, key=lambda item: item[1])
    if probability < minimum_probability:
        return Decision("ask_confirm", ("reward_below_conservative_threshold",), probability, policy_state)
    decision = Decision(action, ("human_preference_reward",), probability, policy_state)
    return apply_safety_constraints(decision, constraints)


def llm_verbalization_payload(decision: Decision, locale: str = "zh-CN") -> dict:
    """The LLM verbalizes a frozen action and cannot alter policy output."""
    return {
        "immutable_action": decision.action,
        "rationale_codes": list(decision.rationale_codes),
        "locale": locale,
        "instruction": "Explain the immutable action briefly. Do not choose or change the action.",
    }
