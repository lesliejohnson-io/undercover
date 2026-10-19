"""The UnderCover backend."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from backend import db, store
from backend.models import (
    Claim,
    Customer,
    DecisionRequest,
    Handler,
    PaymentRequest,
    Policy,
    QueueClaim,
    SignOffRequest,
    Step,
    StepRequest,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create and seed the database before the backend serves anything."""
    db.setup()
    yield


app = FastAPI(title="UnderCover", lifespan=lifespan)


@app.exception_handler(store.Refused)
async def refused(request: Request, exc: Exception) -> JSONResponse:
    """Turn an operation the records do not allow into a 409."""
    return JSONResponse(status_code=409, content={"detail": str(exc)})


def claim_or_404(claim_id: str) -> Claim:
    """Return a claim, or raise a 404 when there is no such claim."""
    claim = store.claim(claim_id)
    if not claim:
        raise HTTPException(404, f"No claim {claim_id}")
    return claim


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
    return claim_or_404(claim_id)


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


@app.post("/api/claims/{claim_id}/activity", operation_id="add_activity")
def add_activity(claim_id: str, body: StepRequest) -> Step:
    """Record one step taken on a claim."""
    claim_or_404(claim_id)
    return store.add_step(claim_id, body.step, body.detail)


@app.post("/api/claims/{claim_id}/decision", operation_id="decide_claim")
def decide_claim(claim_id: str, body: DecisionRequest) -> Claim:
    """Record the decision on a claim, with the payout and the reason for it."""
    claim_or_404(claim_id)
    return store.decide(
        claim_id, body.decision, body.payout, body.reason, body.policy_section
    )


@app.post("/api/claims/{claim_id}/signoff", operation_id="sign_off_claim")
def sign_off_claim(claim_id: str, body: SignOffRequest) -> Claim:
    """Sign off a claim whose payout is over the approval limit."""
    claim_or_404(claim_id)
    return store.sign_off(claim_id, body.handler_id)


@app.post("/api/claims/{claim_id}/payment", operation_id="pay_claim")
def pay_claim(claim_id: str, body: PaymentRequest) -> Claim:
    """Pay an approved claim, unless it is still waiting for a sign-off."""
    claim_or_404(claim_id)
    return store.pay(claim_id, body.amount)
