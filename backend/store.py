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
    Handler,
    Plan,
    Policy,
    QueueClaim,
    Step,
    Trip,
)


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
