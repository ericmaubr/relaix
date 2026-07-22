"""Rule condition evaluation against a JSON payload.

A condition's `field_path` is a dotted path into the payload (e.g.
`message.task.name`). Multiple conditions on the same rule are combined with
AND — evaluating multiple `group_index` values as OR-across-groups is out of
scope for now (see README "Out of scope"): all conditions passed to
`rule_matches` are ANDed together regardless of their group."""

from __future__ import annotations

from relaix.domain import WebhookRuleCondition


def get_field(payload: dict, field_path: str) -> object | None:
    current: object = payload
    for part in field_path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def _to_number(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def evaluate_condition(
    payload: dict, field_path: str, operator: str, expected: str
) -> bool:
    actual = get_field(payload, field_path)

    if operator == "=":
        return actual is not None and str(actual) == expected
    if operator == "!=":
        return actual is None or str(actual) != expected
    if operator == "contains":
        return actual is not None and expected in str(actual)
    if operator == "not_contains":
        return actual is None or expected not in str(actual)
    if operator in (">", ">=", "<", "<="):
        if actual is None:
            return False
        left = _to_number(actual)
        right = _to_number(expected)
        a, b = (
            (left, right)
            if left is not None and right is not None
            else (str(actual), expected)
        )
        if operator == ">":
            return a > b
        if operator == ">=":
            return a >= b
        if operator == "<":
            return a < b
        return a <= b

    raise ValueError(f"Unknown operator: {operator!r}")


def rule_matches(payload: dict, conditions: list[WebhookRuleCondition]) -> bool:
    """A rule with no conditions never matches — conditions must be explicit,
    there's no accidental catch-all."""
    if not conditions:
        return False
    return all(
        evaluate_condition(payload, c.field_path, c.operator, c.value)
        for c in conditions
    )
