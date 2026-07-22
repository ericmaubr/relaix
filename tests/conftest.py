from __future__ import annotations

import pytest

from relaix import db


@pytest.fixture(autouse=True)
def _in_memory_db():
    db.set_database_url("sqlite:///:memory:")
    db.create_schema()
    yield
    db.set_database_url("sqlite:///:memory:")
