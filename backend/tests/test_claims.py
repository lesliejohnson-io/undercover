from fastapi.testclient import TestClient

from backend import db, store
from backend.main import app

client = TestClient(app)


def test_the_seed_loads_the_business_data():
    with db.connection() as conn:
        counts = {
            table: conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]  # noqa: S608
            for table in ("claims", "policies", "customers", "plans", "handlers")
        }
    assert counts == {
        "claims": 25,
        "policies": 50,
        "customers": 49,
        "plans": 3,
        "handlers": 3,
    }


def test_the_queue_starts_with_every_claim_waiting():
    queue = client.get("/api/claims").json()
    assert len(queue) == 25
    assert {claim["status"] for claim in queue} == {"waiting"}
    assert all(claim["decision"] is None for claim in queue)
    first = queue[0]
    assert first["claim_id"] == "CLM-1001"
    assert first["customer_name"] == "Maya Patel"
    assert first["claim_type"] == "trip_delay"
    assert first["submitted_on"] == "2026-06-24"
    assert first["amount_claimed"] == 420.0


def test_a_claim_in_full():
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["policy_id"] == "POL-2001"
    assert claim["incident_location"] == "Rome, Italy"
    assert "canceled by Meridian Air" in claim["story"]
    assert claim["amount_claimed"] == 420.0
    assert [item["amount"] for item in claim["items"]] == [245.0, 95.0, 80.0]
    assert len(claim["documents"]) == 4
    assert "Flight MA 611" in claim["documents"][0]["content"]
    assert claim["decision"] is None


def test_the_policy_behind_a_claim():
    policy = client.get("/api/claims/CLM-1001/policy").json()
    assert policy["policy_id"] == "POL-2001"
    assert policy["plan"] == "premium"
    assert policy["plan_limits"]["trip_delay_waiting_hours"] == 6
    assert policy["plan_limits"]["trip_delay_max"] == 800.0
    assert policy["plan_limits"]["deductible"] == 50.0
    assert policy["deductible_applies_to"] == ["baggage", "emergency_medical"]
    assert policy["trip"]["destination"] == "Rome, Italy"
    assert policy["trip"]["trip_cost"] == 3100.0
    assert policy["travelers"] == ["Maya Patel"]
    assert policy["add_ons"] == []


def test_a_policy_lists_the_add_ons_it_was_bought_with():
    with db.connection() as conn:
        policy_id = conn.execute(
            "SELECT policy_id FROM policies WHERE add_ons LIKE '%electronics_plus%'"
        ).fetchone()["policy_id"]
        claim_id = conn.execute(
            "SELECT claim_id FROM claims WHERE policy_id = :policy_id",
            {"policy_id": policy_id},
        ).fetchone()["claim_id"]
    policy = client.get(f"/api/claims/{claim_id}/policy").json()
    assert [add_on["add_on"] for add_on in policy["add_ons"]] == ["electronics_plus"]
    assert "per-item limit" in policy["add_ons"][0]["effect"]


def test_the_customer_behind_a_claim():
    customer = client.get("/api/claims/CLM-1001/customer").json()
    assert customer["customer_id"] == "CUS-3001"
    assert customer["name"] == "Maya Patel"
    assert customer["address"]["city"] == "Jersey City"
    assert customer["previous_claims"][0]["claim_id"] == "CLM-0412"
    assert customer["previous_claims"][0]["amount_paid"] == 140.0


def test_the_policy_wording():
    response = client.get("/api/policy-wording")
    assert response.status_code == 200
    assert "## 10. How we work out your payment" in response.text
    assert "Per-item limit" in response.text


def test_the_handlers():
    handlers = client.get("/api/handlers").json()
    assert [handler["handler_id"] for handler in handlers] == [
        "HND-01",
        "HND-02",
        "HND-03",
    ]
    assert handlers[0]["name"] == "Dana Whitfield"
    assert handlers[0]["can_approve_over_limit"] is True


def test_an_unknown_claim():
    for route in ("", "/policy", "/customer"):
        response = client.get(f"/api/claims/CLM-9999{route}")
        assert response.status_code == 404
        assert response.json()["detail"] == "No claim CLM-9999"


def test_the_payout_approval_limit_comes_from_the_company_settings():
    assert store.payout_approval_limit() == 1000.0


def test_a_claim_starts_with_no_activity():
    assert client.get("/api/claims/CLM-1001/activity").json() == []


def test_the_handler_lookup():
    assert store.handler("HND-02") is not None
    assert store.handler("HND-99") is None


def test_the_database_is_seeded_once():
    db.setup()
    assert len(client.get("/api/claims").json()) == 25
