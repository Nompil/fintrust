"""Summarize simulator gates for tagged log creation; never perform AWS calls.

A multi-resource simulator run evaluates each action against every supplied ARN.
Its top-level decision may deny because of cross-pairs that the real operation
would not use. This reads the two documented action/resource pairs separately.
It is not a reproduction of CloudWatch Logs' dependent authorization internals.
"""

ACTIONS = ("logs:CreateLogGroup", "logs:TagResource")


def log_creation_gates(response, group_arn):
    """Return each documented gate; absent/conflicting evidence is unknown."""
    if group_arn.endswith(":*") or "*" in group_arn:
        raise ValueError("Supply the exact unsuffixed log-group ARN")
    resources = {ACTIONS[0]: group_arn + ":*", ACTIONS[1]: group_arn}
    gates = {}
    for action, arn in resources.items():
        decisions = []
        for entry in response.get("EvaluationResults", []):
            if entry.get("EvalActionName") != action:
                continue
            specifics = entry.get("ResourceSpecificResults", [])
            if specifics:
                decisions.extend(r.get("EvalResourceDecision") for r in specifics
                                 if r.get("EvalResourceName") == arn)
            elif entry.get("EvalResourceName") == arn:
                decisions.append(entry.get("EvalDecision"))
        unique = set(decisions)
        gates[action] = unique.pop() if len(unique) == 1 else "unknown"
    return {"gates": gates,
            "both_documented_gates_allowed": all(v == "allowed" for v in gates.values())}
