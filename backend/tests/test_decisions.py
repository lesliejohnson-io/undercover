import pytest
from fastapi.testclient import TestClient

from backend import db, store
from backend.main import app

client = TestClient(app)

APPROVE = {
    "decision": "approve",
    "payout": 420.0,
    "reason": "A six hour delay on a Premium plan, hotel and meals receipted.",
    "policy_section": "Section 3",
}
BIG_APPROVE = APPROVE | {"payout": 2400.0}


def decide(claim_id: str, body: dict):
    return client.post(f"/api/claims/{claim_id}/decision", json=body)


def pay(claim_id: str, amount: float):
    return client.post(f"/api/claims/{claim_id}/payment", json={"amount": amount})


def sign_off(claim_id: str, handler_id: str):
    return client.post(
        f"/api/claims/{claim_id}/signoff", json={"handler_id": handler_id}
    )


def test_an_approval_inside_the_limit_is_decided_and_paid():
    claim = decide("CLM-1001", APPROVE).json()
    assert claim["status"] == "decided"
    assert claim["decision"]["payout"] == 420.0
    assert claim["decision"]["policy_section"] == "Section 3"
    assert claim["decision"]["paid_at"] is None

    paid = pay("CLM-1001", 420.0).json()
    assert paid["status"] == "decided"
    assert paid["decision"]["paid_amount"] == 420.0
    assert paid["decision"]["paid_at"]


def test_an_approval_over_the_limit_waits_for_a_sign_off():
    claim = decide("CLM-1001", BIG_APPROVE).json()
    assert claim["status"] == "awaiting_signoff"

    refused = pay("CLM-1001", 2400.0)
    assert refused.status_code == 409
    assert "needs a handler's sign-off" in refused.json()["detail"]
    assert "$1,000.00 approval limit" in refused.json()["detail"]
    assert client.get("/api/claims/CLM-1001").json()["decision"]["paid_at"] is None


def test_a_signed_off_claim_can_be_paid():
    decide("CLM-1001", BIG_APPROVE)
    signed = sign_off("CLM-1001", "HND-01").json()
    assert signed["decision"]["signed_off_by"] == "HND-01"
    assert signed["status"] == "awaiting_signoff"

    paid = pay("CLM-1001", 2400.0).json()
    assert paid["status"] == "decided"
    assert paid["decision"]["paid_amount"] == 2400.0


def test_the_queue_shows_where_a_claim_stands():
    decide("CLM-1001", BIG_APPROVE)
    decide("CLM-1002", {**APPROVE, "payout": 0.0, "decision": "decline"})
    rows = {row["claim_id"]: row for row in client.get("/api/claims").json()}
    assert rows["CLM-1001"]["status"] == "awaiting_signoff"
    assert rows["CLM-1001"]["payout"] == 2400.0
    assert rows["CLM-1002"]["status"] == "decided"
    assert rows["CLM-1002"]["decision"] == "decline"
    assert rows["CLM-1003"]["status"] == "waiting"


@pytest.mark.parametrize("decision", ["decline", "refer"])
def test_declining_and_referring_land_on_decided(decision: str):
    claim = decide("CLM-1001", {**APPROVE, "decision": decision, "payout": 0.0}).json()
    assert claim["status"] == "decided"
    assert claim["decision"]["decision"] == decision
    assert claim["decision"]["payout"] == 0.0


def test_a_claim_that_was_not_approved_is_not_paid():
    decide("CLM-1001", {**APPROVE, "decision": "decline", "payout": 0.0})
    refused = pay("CLM-1001", 0.0)
    assert refused.status_code == 409
    assert "nothing to pay" in refused.json()["detail"]


def test_a_claim_is_paid_once():
    decide("CLM-1001", APPROVE)
    assert pay("CLM-1001", 420.0).status_code == 200
    refused = pay("CLM-1001", 420.0)
    assert refused.status_code == 409
    assert "already paid" in refused.json()["detail"]


def test_a_payment_must_match_the_payout():
    decide("CLM-1001", APPROVE)
    refused = pay("CLM-1001", 900.0)
    assert refused.status_code == 409
    assert "must match the payout of $420.00" in refused.json()["detail"]


def test_a_payout_must_match_the_decision():
    assert decide("CLM-1001", {**APPROVE, "payout": 0.0}).status_code == 409
    assert decide("CLM-1001", {**APPROVE, "decision": "refer"}).status_code == 409


def test_a_claim_is_decided_once():
    assert decide("CLM-1001", APPROVE).status_code == 200
    refused = decide("CLM-1001", APPROVE)
    assert refused.status_code == 409
    assert "already decided" in refused.json()["detail"]


def test_a_claim_with_no_decision_cannot_be_paid():
    refused = pay("CLM-1001", 420.0)
    assert refused.status_code == 409
    assert "no decision yet" in refused.json()["detail"]


def test_only_a_claim_over_the_limit_is_signed_off():
    decide("CLM-1001", APPROVE)
    refused = sign_off("CLM-1001", "HND-01")
    assert refused.status_code == 409
    assert "not waiting for a sign-off" in refused.json()["detail"]


def test_an_unknown_handler_cannot_sign_off():
    decide("CLM-1001", BIG_APPROVE)
    refused = sign_off("CLM-1001", "HND-99")
    assert refused.status_code == 409
    assert refused.json()["detail"] == "No handler HND-99"


def test_the_write_operations_404_on_an_unknown_claim():
    assert decide("CLM-9999", APPROVE).status_code == 404
    assert pay("CLM-9999", 1.0).status_code == 404
    assert sign_off("CLM-9999", "HND-01").status_code == 404
    assert (
        client.post(
            "/api/claims/CLM-9999/activity", json={"step": "a", "detail": "b"}
        ).status_code
        == 404
    )


def test_the_activity_is_replayed_in_order():
    client.post(
        "/api/claims/CLM-1001/activity",
        json={"step": "Read the claim", "detail": "420.00 claimed"},
    )
    client.post(
        "/api/claims/CLM-1001/activity",
        json={"step": "Read the policy", "detail": "Premium"},
    )
    decide("CLM-1001", BIG_APPROVE)
    pay("CLM-1001", 2400.0)
    sign_off("CLM-1001", "HND-02")
    pay("CLM-1001", 2400.0)
    steps = [
        step["step"] for step in client.get("/api/claims/CLM-1001/activity").json()
    ]
    assert steps == [
        "Read the claim",
        "Read the policy",
        "Decision",
        "Payment blocked",
        "Signed off",
        "Paid",
    ]


def test_the_guard_follows_the_limit_in_the_company_settings():
    with db.connection() as conn:
        conn.execute(
            "UPDATE settings SET value = '300' WHERE key = 'payout_approval_limit'"
        )
    assert store.payout_approval_limit() == 300.0
    claim = decide("CLM-1001", APPROVE).json()
    assert claim["status"] == "awaiting_signoff"
    assert pay("CLM-1001", 420.0).status_code == 409


def test_starting_a_claim_clears_an_earlier_run():
    client.post(
        "/api/claims/CLM-1001/activity",
        json={"step": "Read the claim", "detail": "once"},
    )
    decide("CLM-1001", {**APPROVE, "decision": "refer", "payout": 0.0})
    claim = store.start("CLM-1001")
    assert claim.status == "in_progress"
    assert claim.decision is None
    assert [step.step for step in store.activity("CLM-1001")] == ["Started"]


def test_a_paid_claim_is_not_worked_again():
    decide("CLM-1001", APPROVE)
    pay("CLM-1001", 420.0)
    with pytest.raises(store.Refused, match="is paid"):
        store.start("CLM-1001")


def test_an_unknown_claim_is_refused_in_the_store():
    with pytest.raises(store.Refused, match="No claim CLM-9999"):
        store.must("CLM-9999")
