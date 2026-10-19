"""The shapes the UnderCover API returns and accepts."""

from typing import Literal

from pydantic import BaseModel

ClaimStatus = Literal["waiting", "in_progress", "awaiting_signoff", "decided"]
DecisionName = Literal["approve", "decline", "refer"]


class Item(BaseModel):
    """One line the customer is claiming for."""

    description: str
    category: str
    amount: float


class Document(BaseModel):
    """One supporting document, as text."""

    name: str
    type: str
    content: str


class Decision(BaseModel):
    """The decision on a claim, with its payout, sign-off and payment."""

    decision: DecisionName
    payout: float
    reason: str
    policy_section: str
    decided_at: str
    signed_off_by: str | None
    signed_off_at: str | None
    paid_amount: float | None
    paid_at: str | None


class QueueClaim(BaseModel):
    """One row of the claims queue."""

    claim_id: str
    customer_id: str
    customer_name: str
    claim_type: str
    summary: str
    submitted_on: str
    amount_claimed: float
    status: ClaimStatus
    decision: DecisionName | None
    payout: float | None


class Claim(BaseModel):
    """A claim in full, with the decision on it when there is one."""

    claim_id: str
    policy_id: str
    customer_id: str
    customer_name: str
    claim_type: str
    submitted_on: str
    incident_date: str
    incident_location: str
    summary: str
    story: str
    items: list[Item]
    amount_claimed: float
    documents: list[Document]
    status: ClaimStatus
    decision: Decision | None


class Plan(BaseModel):
    """A plan's limits, waiting periods and deductible."""

    plan: str
    name: str
    trip_cancellation_max: float
    trip_delay_waiting_hours: int
    trip_delay_max: float
    baggage_delay_waiting_hours: int
    baggage_delay_max: float
    baggage_max: float
    per_item_limit: float
    passport_max: float
    emergency_medical_max: float
    deductible: float


class AddOn(BaseModel):
    """An add-on bought on a policy, and what it changes."""

    add_on: str
    name: str
    effect: str


class Trip(BaseModel):
    """The trip a policy covers."""

    destination: str
    departs_on: str
    returns_on: str
    trip_cost: float


class Policy(BaseModel):
    """A policy, with the limits of the plan it was bought on."""

    policy_id: str
    customer_id: str
    plan: str
    plan_limits: Plan
    add_ons: list[AddOn]
    purchased_on: str
    sold_through: str
    trip: Trip
    travelers: list[str]
    status: str
    deductible_applies_to: list[str]


class PreviousClaim(BaseModel):
    """An earlier claim in a customer's history."""

    claim_id: str
    filed_on: str
    incident_date: str
    claim_type: str
    summary: str
    outcome: str
    amount_paid: float


class Address(BaseModel):
    """A customer's address."""

    street: str
    city: str
    state: str
    zip: str


class Customer(BaseModel):
    """A customer and their claim history."""

    customer_id: str
    name: str
    email: str
    phone: str
    date_of_birth: str
    address: Address
    customer_since: str
    previous_claims: list[PreviousClaim]


class Handler(BaseModel):
    """A claims handler."""

    handler_id: str
    name: str
    role: str
    email: str
    can_approve_over_limit: bool


class Step(BaseModel):
    """One step the agent took on a claim."""

    step: str
    detail: str
    at: str
