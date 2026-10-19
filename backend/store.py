"""Reading and writing UnderCover's records."""

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any

from backend import db
from backend.models import (
    AddOn,
    Claim,
    Customer,
    Decision,
    DecisionName,
    Handler,
    Plan,
    Policy,
    QueueClaim,
    Step,
    Trip,
)


class Refused(Exception):
    """An operation the records do not allow."""


def setting(key: str) -> Any:
    """Return one of the company settings."""
    with db.connection() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = :key", {"key": key}
        ).fetchone()
    return json.loads(row["value"])


def payout_approval_limit() -> float:
    """Return the payout above which a claim needs a handler's sign-off."""
    return float(setting("payout_approval_limit"))


def queue() -> list[QueueClaim]:
    """Return the claims queue, newest claim first."""
    with db.connection() as conn:
        rows = conn.execute(
            """SELECT c.*, u.name AS customer_name FROM claims c
               JOIN customers u ON u.customer_id = c.customer_id
               ORDER BY c.claim_id"""
        ).fetchall()
    return [QueueClaim(**dict(row)) for row in rows]


def claim(claim_id: str) -> Claim | None:
    """Return one claim in full, or None when there is no such claim."""
    with db.connection() as conn:
        row = conn.execute(
            """SELECT c.*, u.name AS customer_name FROM claims c
               JOIN customers u ON u.customer_id = c.customer_id
               WHERE c.claim_id = :claim_id""",
            {"claim_id": claim_id},
        ).fetchone()
    if not row:
        return None
    fields = dict(row)
    fields["items"] = json.loads(fields["items"])
    fields["documents"] = json.loads(fields["documents"])
    fields["decision"] = Decision(**fields) if fields["decision"] else None
    return Claim(**fields)


def policy_for(claim_id: str) -> Policy | None:
    """Return the policy a claim was made on, with its plan's limits."""
    with db.connection() as conn:
        row = conn.execute(
            """SELECT p.* FROM policies p
               JOIN claims c ON c.policy_id = p.policy_id
               WHERE c.claim_id = :claim_id""",
            {"claim_id": claim_id},
        ).fetchone()
        if not row:
            return None
        plan = conn.execute(
            "SELECT * FROM plans WHERE plan = :plan", {"plan": row["plan"]}
        ).fetchone()
        add_ons = conn.execute(
            "SELECT add_on, name, effect FROM add_ons ORDER BY add_on"
        ).fetchall()
    bought = json.loads(row["add_ons"])
    return Policy(
        policy_id=row["policy_id"],
        customer_id=row["customer_id"],
        plan=row["plan"],
        plan_limits=Plan(**dict(plan)),
        add_ons=[AddOn(**dict(a)) for a in add_ons if a["add_on"] in bought],
        purchased_on=row["purchased_on"],
        sold_through=row["sold_through"],
        trip=Trip(
            destination=row["destination"],
            departs_on=row["departs_on"],
            returns_on=row["returns_on"],
            trip_cost=row["trip_cost"],
        ),
        travelers=json.loads(row["travelers"]),
        status=row["status"],
        deductible_applies_to=setting("deductible_applies_to"),
    )


def customer_for(claim_id: str) -> Customer | None:
    """Return the customer who made a claim, with their claim history."""
    with db.connection() as conn:
        row = conn.execute(
            """SELECT u.* FROM customers u
               JOIN claims c ON c.customer_id = u.customer_id
               WHERE c.claim_id = :claim_id""",
            {"claim_id": claim_id},
        ).fetchone()
    if not row:
        return None
    fields = dict(row)
    fields["address"] = json.loads(fields["address"])
    fields["previous_claims"] = json.loads(fields["previous_claims"])
    return Customer(**fields)


def handlers() -> list[Handler]:
    """Return the claims handlers."""
    with db.connection() as conn:
        rows = conn.execute("SELECT * FROM handlers ORDER BY handler_id").fetchall()
    return [Handler(**dict(row)) for row in rows]


def handler(handler_id: str) -> Handler | None:
    """Return one claims handler, or None when there is no such handler."""
    with db.connection() as conn:
        row = conn.execute(
            "SELECT * FROM handlers WHERE handler_id = :handler_id",
            {"handler_id": handler_id},
        ).fetchone()
    return Handler(**dict(row)) if row else None


def activity(claim_id: str) -> list[Step]:
    """Return the steps taken on a claim, in the order they happened."""
    with db.connection() as conn:
        rows = conn.execute(
            """SELECT step, detail, at FROM activity
               WHERE claim_id = :claim_id ORDER BY id""",
            {"claim_id": claim_id},
        ).fetchall()
    return [Step(**dict(row)) for row in rows]


def add_step(claim_id: str, step: str, detail: str) -> Step:
    """Record one step taken on a claim."""
    at = now()
    with db.connection() as conn:
        _add_step(conn, claim_id, step, detail, at)
    return Step(step=step, detail=detail, at=at)


def _add_step(
    conn: sqlite3.Connection, claim_id: str, step: str, detail: str, at: str
) -> None:
    conn.execute(
        """INSERT INTO activity (claim_id, step, detail, at)
           VALUES (:claim_id, :step, :detail, :at)""",
        {"claim_id": claim_id, "step": step, "detail": detail, "at": at},
    )


def now() -> str:
    """Return the current time, to the second, as text."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def start(claim_id: str) -> Claim:
    """Hand a claim to the agent, clearing anything an earlier run left."""
    current = must(claim_id)
    if current.decision and current.decision.paid_at:
        raise Refused(f"{claim_id} is paid and cannot be worked again")
    with db.connection() as conn:
        conn.execute(
            """UPDATE claims SET status = 'in_progress', decision = NULL,
               payout = NULL, reason = NULL, policy_section = NULL,
               decided_at = NULL, signed_off_by = NULL, signed_off_at = NULL
               WHERE claim_id = :claim_id""",
            {"claim_id": claim_id},
        )
        conn.execute(
            "DELETE FROM activity WHERE claim_id = :claim_id", {"claim_id": claim_id}
        )
        _add_step(conn, claim_id, "Started", f"Working {claim_id}", now())
    return must(claim_id)


def decide(
    claim_id: str,
    decision: DecisionName,
    payout: float,
    reason: str,
    policy_section: str,
) -> Claim:
    """Record the decision on a claim and set where it now stands."""
    current = must(claim_id)
    if current.decision:
        raise Refused(f"{claim_id} is already decided")
    if decision == "approve" and payout <= 0:
        raise Refused("An approved claim needs a payout above $0")
    if decision != "approve" and payout != 0:
        raise Refused("Only an approved claim has a payout")
    over_limit = decision == "approve" and payout > payout_approval_limit()
    status = "awaiting_signoff" if over_limit else "decided"
    at = now()
    with db.connection() as conn:
        conn.execute(
            """UPDATE claims SET decision = :decision, payout = :payout,
               reason = :reason, policy_section = :policy_section,
               decided_at = :at, status = :status WHERE claim_id = :claim_id""",
            {
                "claim_id": claim_id,
                "decision": decision,
                "payout": payout,
                "reason": reason,
                "policy_section": policy_section,
                "at": at,
                "status": status,
            },
        )
        _add_step(conn, claim_id, "Decision", f"{decision} {money(payout)}", at)
    return must(claim_id)


def sign_off(claim_id: str, handler_id: str) -> Claim:
    """Sign off a claim that is over the payout approval limit."""
    current = must(claim_id)
    if current.status != "awaiting_signoff":
        raise Refused(f"{claim_id} is not waiting for a sign-off")
    signer = handler(handler_id)
    if not signer:
        raise Refused(f"No handler {handler_id}")
    at = now()
    with db.connection() as conn:
        conn.execute(
            """UPDATE claims SET signed_off_by = :handler_id, signed_off_at = :at
               WHERE claim_id = :claim_id""",
            {"claim_id": claim_id, "handler_id": handler_id, "at": at},
        )
        _add_step(conn, claim_id, "Signed off", f"{signer.name} signed off", at)
    return must(claim_id)


def pay(claim_id: str, amount: float) -> Claim:
    """Pay an approved claim, unless it is still waiting for a sign-off."""
    refusal = refusal_to_pay(must(claim_id), amount)
    if refusal:
        add_step(claim_id, "Payment blocked", refusal)
        raise Refused(refusal)
    at = now()
    with db.connection() as conn:
        conn.execute(
            """UPDATE claims SET paid_amount = :amount, paid_at = :at,
               status = 'decided' WHERE claim_id = :claim_id""",
            {"claim_id": claim_id, "amount": amount, "at": at},
        )
        _add_step(conn, claim_id, "Paid", money(amount), at)
    return must(claim_id)


def refusal_to_pay(current: Claim, amount: float) -> str:
    """Say why a claim cannot be paid, or return an empty string when it can."""
    decision = current.decision
    if not decision:
        raise Refused(f"{current.claim_id} has no decision yet")
    if decision.decision != "approve":
        return f"{current.claim_id} was not approved, so there is nothing to pay"
    if decision.paid_at:
        return f"{current.claim_id} was already paid"
    if amount != decision.payout:
        return f"The payment must match the payout of {money(decision.payout)}"
    limit = payout_approval_limit()
    if amount > limit and not decision.signed_off_at:
        return (
            f"{money(amount)} is over the {money(limit)} approval limit "
            "and needs a handler's sign-off"
        )
    return ""


def must(claim_id: str) -> Claim:
    """Return a claim, refusing the operation when there is no such claim."""
    found = claim(claim_id)
    if not found:
        raise Refused(f"No claim {claim_id}")
    return found


def money(amount: float) -> str:
    """Format an amount in US dollars."""
    return f"${amount:,.2f}"
