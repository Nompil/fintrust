"""Approved role separation and actionable admission errors; no AWS."""
import io
import pytest
from tests.test_release1_end_to_end import release_db, authenticated_client
from tests.test_frontend_workflows import local_receipts

@pytest.mark.parametrize("role",["Admin","Read-only/Auditor"])
def test_upload_denied_before_validation(release_db,authenticated_client,local_receipts,role):
    client,headers=authenticated_client
    assert client.post("/v1/upload",headers=headers(role),data={}).status_code==403

@pytest.mark.parametrize("role",["Admin","Risk/Compliance Analyst","Read-only/Auditor"])
def test_recovery_only_maintainer(release_db,authenticated_client,role):
    client,headers=authenticated_client
    assert client.post("/v1/operations/retry",headers=headers(role),json={}).status_code==403

def test_old_csv_actionable_safe_header_detail(release_db,authenticated_client,local_receipts):
    client,headers=authenticated_client
    data=b"account_id,amount,currency,merchant,tx_date,tx_type,country\n1,20,ZAR,test,2026-10-01,debit,ZA"
    response=client.post("/v1/upload",headers=headers("Risk/Compliance Analyst"),data={"file":(io.BytesIO(data),"old.csv")})
    assert response.status_code==400
    assert response.json["reason_code"]=="INVALID_CSV_SCHEMA"
    assert "source_system" in response.json["detail"] and "source_transaction_id" in response.json["detail"]
    assert "old.csv" not in response.json["detail"] and "SELECT" not in response.json["detail"]
