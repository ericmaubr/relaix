from __future__ import annotations

from relaix.domain import WebhookRuleCondition
from relaix.matching import evaluate_condition, get_field, rule_matches

PAYLOAD = {
    "message": {
        "name": "extrato SIMPLES",
        "task": {"name": "Teste - pagamento"},
    },
    "count": "10",
}


def test_get_field_dotted_path():
    assert get_field(PAYLOAD, "message.name") == "extrato SIMPLES"
    assert get_field(PAYLOAD, "message.task.name") == "Teste - pagamento"


def test_get_field_missing_path_returns_none():
    assert get_field(PAYLOAD, "message.missing") is None
    assert get_field(PAYLOAD, "message.name.too.deep") is None


def test_operator_equals():
    assert evaluate_condition(PAYLOAD, "message.name", "=", "extrato SIMPLES") is True
    assert evaluate_condition(PAYLOAD, "message.name", "=", "other") is False


def test_operator_not_equals():
    assert evaluate_condition(PAYLOAD, "message.name", "!=", "other") is True
    assert evaluate_condition(PAYLOAD, "message.missing", "!=", "anything") is True


def test_operator_contains():
    assert (
        evaluate_condition(PAYLOAD, "message.task.name", "contains", "pagamento")
        is True
    )
    assert evaluate_condition(PAYLOAD, "message.task.name", "contains", "nope") is False


def test_operator_not_contains():
    assert (
        evaluate_condition(PAYLOAD, "message.task.name", "not_contains", "nope") is True
    )
    assert evaluate_condition(PAYLOAD, "message.missing", "not_contains", "x") is True


def test_operator_numeric_comparison():
    assert evaluate_condition(PAYLOAD, "count", ">", "5") is True
    assert evaluate_condition(PAYLOAD, "count", "<", "5") is False
    assert evaluate_condition(PAYLOAD, "count", ">=", "10") is True
    assert evaluate_condition(PAYLOAD, "count", "<=", "9") is False


def test_operator_comparison_falls_back_to_string():
    payload = {"date": "2026-07-22"}
    assert evaluate_condition(payload, "date", ">", "2026-01-01") is True
    assert evaluate_condition(payload, "date", "<", "2026-01-01") is False


def test_unknown_operator_raises():
    import pytest

    with pytest.raises(ValueError):
        evaluate_condition(PAYLOAD, "message.name", "??", "x")


def _cond(field_path, operator, value, group_index=0):
    return WebhookRuleCondition(
        id="c",
        rule_id="r",
        group_index=group_index,
        field_path=field_path,
        operator=operator,
        value=value,
    )


def test_rule_matches_requires_all_conditions():
    conditions = [
        _cond("message.name", "=", "extrato SIMPLES"),
        _cond("message.task.name", "contains", "pagamento"),
    ]
    assert rule_matches(PAYLOAD, conditions) is True

    conditions_partial_fail = [
        _cond("message.name", "=", "extrato SIMPLES"),
        _cond("message.task.name", "contains", "nope"),
    ]
    assert rule_matches(PAYLOAD, conditions_partial_fail) is False


def test_rule_with_no_conditions_never_matches():
    assert rule_matches(PAYLOAD, []) is False
