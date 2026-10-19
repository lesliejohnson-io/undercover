"""The UnderCover backend."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse

from backend import db, store
from backend.models import Claim, Customer, Handler, Policy, QueueClaim, Step


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create and seed the database before the backend serves anything."""
    db.setup()
    yield


app = FastAPI(title="UnderCover", lifespan=lifespan)


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


@app.get("/api/claims", operation_id="list_claims")
def list_claims() -> list[QueueClaim]:
    """List every claim in the queue with where it stands."""
    return store.queue()


@app.get("/api/claims/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str) -> Claim:
    """Read one claim in full, with the decision on it when there is one."""
    claim = store.claim(claim_id)
    if not claim:
        raise HTTPException(404, f"No claim {claim_id}")
    return claim


@app.get("/api/claims/{claim_id}/policy", operation_id="get_claim_policy")
def get_claim_policy(claim_id: str) -> Policy:
    """Read the policy a claim was made on, with its plan's limits."""
    policy = store.policy_for(claim_id)
    if not policy:
        raise HTTPException(404, f"No claim {claim_id}")
    return policy


@app.get("/api/claims/{claim_id}/customer", operation_id="get_claim_customer")
def get_claim_customer(claim_id: str) -> Customer:
    """Read the customer who made a claim, with their claim history."""
    customer = store.customer_for(claim_id)
    if not customer:
        raise HTTPException(404, f"No claim {claim_id}")
    return customer


@app.get(
    "/api/policy-wording",
    operation_id="get_policy_wording",
    response_class=PlainTextResponse,
)
def get_policy_wording() -> str:
    """Read the policy wording, the contract with the customer."""
    return db.policy_wording()


@app.get("/api/claims/{claim_id}/activity", operation_id="list_activity")
def list_activity(claim_id: str) -> list[Step]:
    """List the steps taken on a claim, in the order they happened."""
    return store.activity(claim_id)


@app.get("/api/handlers", operation_id="list_handlers")
def list_handlers() -> list[Handler]:
    """List the claims handlers."""
    return store.handlers()
