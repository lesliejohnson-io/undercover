"""Fixtures shared by the backend and the agent tests."""

from pathlib import Path

import pytest

from backend import db


@pytest.fixture(autouse=True)
def database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Give every test its own database, seeded from data/."""
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "undercover.db"))
    db.setup()
