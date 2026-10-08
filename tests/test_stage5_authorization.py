"""Regress two-gate interpretation, not an imitation of AWS authorization."""
import pytest
from tools.stage5_authorization import ACTIONS, log_creation_gates

ARN = "arn:aws:logs:af-south-1:966467878406:log-group:/aws/lambda/fintrust-ingest-dev"


def response(create="allowed", tag="allowed"):
    # AWS returns cross-product resource results for multi-resource simulations.
    return {"EvaluationResults": [
        {"EvalActionName": ACTIONS[0], "EvalDecision": "implicitDeny",
         "ResourceSpecificResults": [
             {"EvalResourceName": ARN + ":*", "EvalResourceDecision": create},
             {"EvalResourceName": ARN, "EvalResourceDecision": "implicitDeny"}]},
        {"EvalActionName": ACTIONS[1], "EvalDecision": "implicitDeny",
         "ResourceSpecificResults": [
             {"EvalResourceName": ARN + ":*", "EvalResourceDecision": "implicitDeny"},
             {"EvalResourceName": ARN, "EvalResourceDecision": tag}]}]}


@pytest.mark.parametrize("create,tag,expected", [
    ("allowed", "allowed", True),
    ("implicitDeny", "allowed", False),
    ("allowed", "implicitDeny", False),
    ("explicitDeny", "allowed", False),
    ("implicitDeny", "implicitDeny", False),
])
def test_tagging_allow_alone_does_not_prove_create_permission(create, tag, expected):
    result = log_creation_gates(response(create, tag), ARN)
    assert result["gates"] == {ACTIONS[0]: create, ACTIONS[1]: tag}
    assert result["both_documented_gates_allowed"] is expected


def test_aggregate_cross_product_deny_is_not_the_operation_result():
    result = log_creation_gates(response(), ARN)
    assert result["both_documented_gates_allowed"] is True
    # This summarizes supplied independent gates; it never claims live API success.


def test_missing_or_wrong_resource_evidence_is_unknown():
    missing = log_creation_gates({"EvaluationResults": []}, ARN)
    assert set(missing["gates"].values()) == {"unknown"}
    wrong = log_creation_gates(response(), ARN.replace("ingest", "report"))
    assert set(wrong["gates"].values()) == {"unknown"}
    assert wrong["both_documented_gates_allowed"] is False


def test_single_resource_results_are_supported():
    data = {"EvaluationResults": [
        {"EvalActionName": ACTIONS[0], "EvalResourceName": ARN + ":*", "EvalDecision": "allowed"},
        {"EvalActionName": ACTIONS[1], "EvalResourceName": ARN, "EvalDecision": "allowed"}]}
    assert log_creation_gates(data, ARN)["both_documented_gates_allowed"] is True


@pytest.mark.parametrize("arn", [ARN + ":*", ARN.replace("fintrust-ingest-dev", "*")])
def test_summary_cannot_take_a_wildcard_resource(arn):
    with pytest.raises(ValueError):
        log_creation_gates(response(), arn)
