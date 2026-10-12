import copy
import pytest
from tools.serve_release1_demo import validate_reused_identity


def registry():
    return {"principals": [{"subject": "analyst01", "role": "Risk/Compliance Analyst", "status": "ACTIVE", "token_sha256": "a" * 64, "accounts": []}]}


def test_restart_preserves_existing_identity():
    value = registry()
    before = copy.deepcopy(value)
    validate_reused_identity(value, "analyst01", "Risk/Compliance Analyst")
    assert value == before


@pytest.mark.parametrize("change", ["missing", "inactive", "wrong_role", "empty_credential", "duplicate_credential"])
def test_restart_fails_closed(change):
    value = registry()
    principal = value["principals"][0]
    if change == "missing": value["principals"] = []
    elif change == "inactive": principal["status"] = "DISABLED"
    elif change == "wrong_role": principal["role"] = "Admin"
    elif change == "empty_credential": principal["token_sha256"] = ""
    else: value["principals"].append({**principal, "subject": "another-user"})
    with pytest.raises(ValueError):
        validate_reused_identity(value, "analyst01", "Risk/Compliance Analyst")
