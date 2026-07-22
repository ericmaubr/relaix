from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from relaix.http_server import app, set_api_token


@pytest.fixture(autouse=True)
def _no_token():
    set_api_token(None)
    yield
    set_api_token(None)


@pytest.fixture
def client():
    return TestClient(app)


def test_version(client):
    resp = client.get("/version")
    assert resp.status_code == 200
    assert "version" in resp.json()


def test_source_crud(client):
    resp = client.post(
        "/sources", json={"name": "Source A", "api_url": "https://example.com"}
    )
    assert resp.status_code == 200
    source = resp.json()
    assert source["name"] == "Source A"
    source_id = source["id"]

    resp = client.get(f"/sources/{source_id}")
    assert resp.status_code == 200

    resp = client.get("/sources")
    assert resp.status_code == 200
    assert any(s["id"] == source_id for s in resp.json())

    resp = client.patch(f"/sources/{source_id}", json={"active": False})
    assert resp.status_code == 200
    assert resp.json()["active"] is False

    resp = client.delete(f"/sources/{source_id}")
    assert resp.status_code == 204

    resp = client.get(f"/sources/{source_id}")
    assert resp.status_code == 404


def test_rule_crud_with_conditions(client):
    source = client.post(
        "/sources", json={"name": "Source A", "api_url": "https://example.com"}
    ).json()

    resp = client.post(
        "/rules",
        json={
            "name": "Rule A",
            "source_id": source["id"],
            "action_url": "https://internal/action",
            "conditions": [
                {"field_path": "message.name", "operator": "=", "value": "expected"}
            ],
        },
    )
    assert resp.status_code == 200
    rule = resp.json()
    assert len(rule["conditions"]) == 1
    rule_id = rule["id"]

    resp = client.get(f"/rules/{rule_id}")
    assert resp.status_code == 200
    assert resp.json()["conditions"][0]["field_path"] == "message.name"

    resp = client.put(
        f"/rules/{rule_id}/conditions",
        json=[{"field_path": "message.other", "operator": "contains", "value": "x"}],
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    resp = client.delete(f"/rules/{rule_id}")
    assert resp.status_code == 204


def test_rule_rejects_invalid_operator(client):
    source = client.post(
        "/sources", json={"name": "Source A", "api_url": "https://example.com"}
    ).json()
    resp = client.post(
        "/rules",
        json={
            "name": "Rule A",
            "source_id": source["id"],
            "action_url": "https://internal/action",
            "conditions": [
                {"field_path": "message.name", "operator": "??", "value": "x"}
            ],
        },
    )
    assert resp.status_code == 422


def test_events_and_polling_log_endpoints_are_empty_by_default(client):
    assert client.get("/events").json() == []
    assert client.get("/polling-log").json() == []


def test_auth_required_when_token_configured(client):
    set_api_token("secret")
    resp = client.get("/sources")
    assert resp.status_code == 401

    resp = client.get("/sources", headers={"Authorization": "Bearer secret"})
    assert resp.status_code == 200
