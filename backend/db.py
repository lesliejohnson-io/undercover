"""The UnderCover database, seeded from data/."""

import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DEFAULT_PATH = ROOT / "backend" / "undercover.db"

SCHEMA = """
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE plans (
    plan TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    trip_cancellation_max REAL NOT NULL,
    trip_delay_waiting_hours INTEGER NOT NULL,
    trip_delay_max REAL NOT NULL,
    baggage_delay_waiting_hours INTEGER NOT NULL,
    baggage_delay_max REAL NOT NULL,
    baggage_max REAL NOT NULL,
    per_item_limit REAL NOT NULL,
    passport_max REAL NOT NULL,
    emergency_medical_max REAL NOT NULL,
    deductible REAL NOT NULL
);

CREATE TABLE add_ons (
    add_on TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    effect TEXT NOT NULL,
    electronics_per_item_limit REAL
);

CREATE TABLE customers (
    customer_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT NOT NULL,
    date_of_birth TEXT NOT NULL,
    address TEXT NOT NULL,
    customer_since TEXT NOT NULL,
    previous_claims TEXT NOT NULL
);

CREATE TABLE policies (
    policy_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    plan TEXT NOT NULL,
    add_ons TEXT NOT NULL,
    purchased_on TEXT NOT NULL,
    sold_through TEXT NOT NULL,
    destination TEXT NOT NULL,
    departs_on TEXT NOT NULL,
    returns_on TEXT NOT NULL,
    trip_cost REAL NOT NULL,
    travelers TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE handlers (
    handler_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    email TEXT NOT NULL,
    can_approve_over_limit INTEGER NOT NULL
);

CREATE TABLE claims (
    claim_id TEXT PRIMARY KEY,
    policy_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    claim_type TEXT NOT NULL,
    submitted_on TEXT NOT NULL,
    incident_date TEXT NOT NULL,
    incident_location TEXT NOT NULL,
    summary TEXT NOT NULL,
    story TEXT NOT NULL,
    items TEXT NOT NULL,
    amount_claimed REAL NOT NULL,
    documents TEXT NOT NULL,
    status TEXT NOT NULL,
    decision TEXT,
    payout REAL,
    reason TEXT,
    policy_section TEXT,
    decided_at TEXT,
    signed_off_by TEXT,
    signed_off_at TEXT,
    paid_amount REAL,
    paid_at TEXT
);

CREATE TABLE activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id TEXT NOT NULL,
    step TEXT NOT NULL,
    detail TEXT NOT NULL,
    at TEXT NOT NULL
);
"""


def path() -> Path:
    """Return the path of the database file."""
    return Path(os.getenv("UNDERCOVER_DB") or DEFAULT_PATH)


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    """Open a connection to the database and commit on the way out."""
    conn = sqlite3.connect(path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def setup() -> None:
    """Create the database and seed it from data/ unless it is already there."""
    with connection() as conn:
        seeded = conn.execute(
            "SELECT name FROM sqlite_master WHERE name = 'claims'"
        ).fetchone()
        if not seeded:
            conn.executescript(SCHEMA)
            seed(conn)


def policy_wording() -> str:
    """Return the policy wording, the contract with the customer."""
    return (DATA / "policy_wording.md").read_text(encoding="utf-8")


def seed(conn: sqlite3.Connection) -> None:
    """Fill an empty database from the business data in data/."""
    conn.executemany(
        "INSERT INTO settings (key, value) VALUES (:key, :value)",
        [
            {"key": key, "value": json.dumps(value)}
            for key, value in load("company.json").items()
        ],
    )
    plans = load("plans.json")
    conn.execute(
        "INSERT INTO settings (key, value) VALUES ('deductible_applies_to', :value)",
        {"value": json.dumps(plans["deductible_applies_to"])},
    )
    conn.executemany(
        """INSERT INTO plans VALUES (:plan, :name, :trip_cancellation_max,
           :trip_delay_waiting_hours, :trip_delay_max, :baggage_delay_waiting_hours,
           :baggage_delay_max, :baggage_max, :per_item_limit, :passport_max,
           :emergency_medical_max, :deductible)""",
        plans["plans"],
    )
    conn.executemany(
        "INSERT INTO add_ons VALUES (:add_on, :name, :effect, :limit)",
        [
            {
                "add_on": add_on["add_on"],
                "name": add_on["name"],
                "effect": add_on["effect"],
                "limit": add_on.get("electronics_per_item_limit"),
            }
            for add_on in plans["add_ons"]
        ],
    )
    conn.executemany(
        """INSERT INTO customers VALUES (:customer_id, :name, :email, :phone,
           :date_of_birth, :address, :customer_since, :previous_claims)""",
        [
            customer
            | {
                "address": json.dumps(customer["address"]),
                "previous_claims": json.dumps(customer["previous_claims"]),
            }
            for customer in load("customers.json")
        ],
    )
    conn.executemany(
        """INSERT INTO policies VALUES (:policy_id, :customer_id, :plan, :add_ons,
           :purchased_on, :sold_through, :destination, :departs_on, :returns_on,
           :trip_cost, :travelers, :status)""",
        [
            policy
            | policy["trip"]
            | {
                "add_ons": json.dumps(policy["add_ons"]),
                "travelers": json.dumps(policy["travelers"]),
            }
            for policy in load("policies.json")
        ],
    )
    conn.executemany(
        """INSERT INTO handlers VALUES (:handler_id, :name, :role, :email,
           :can_approve_over_limit)""",
        load("handlers.json"),
    )
    conn.executemany(
        """INSERT INTO claims (claim_id, policy_id, customer_id, claim_type,
           submitted_on, incident_date, incident_location, summary, story, items,
           amount_claimed, documents, status)
           VALUES (:claim_id, :policy_id, :customer_id, :claim_type, :submitted_on,
           :incident_date, :incident_location, :summary, :story, :items,
           :amount_claimed, :documents, 'waiting')""",
        [
            claim
            | {
                "items": json.dumps(claim["items"]),
                "documents": json.dumps(claim["documents"]),
            }
            for claim in load("claims.json")
        ],
    )


def load(name: str) -> Any:
    """Read one of the business data files in data/."""
    return json.loads((DATA / name).read_text(encoding="utf-8"))
