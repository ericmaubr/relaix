"""HTTP API via FastAPI."""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from relaix import api

_STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="relaix",
    description="Generic webhook polling and rule-based dispatch service.",
    version="0.1.0",
)

_api_token: str | None = None


def set_api_token(token: str) -> None:
    global _api_token
    _api_token = token


def _configured_token() -> str | None:
    return _api_token or os.environ.get("RELAIX_API_TOKEN")


def verify_token(authorization: str | None = Header(default=None)) -> None:
    expected = _configured_token()
    if expected is None:
        # No token configured: service runs without authentication (local/dev use).
        return
    received = (authorization or "").removeprefix("Bearer ").strip()
    if received != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing token")


class ConditionRequest(BaseModel):
    group_index: int = 0
    field_path: str
    operator: str
    value: str


class SourceRequest(BaseModel):
    name: str
    api_url: str
    kind: str = "webhook_site"
    api_token: str | None = None
    channel_id: str | None = None
    polling_interval_seconds: int = 300


class SourceUpdateRequest(BaseModel):
    name: str | None = None
    api_url: str | None = None
    api_token: str | None = None
    channel_id: str | None = None
    polling_interval_seconds: int | None = None
    active: bool | None = None


class RuleRequest(BaseModel):
    name: str
    source_id: str
    action_url: str
    action_token: str | None = None
    conditions: list[ConditionRequest] = []


class RuleUpdateRequest(BaseModel):
    name: str | None = None
    action_url: str | None = None
    action_token: str | None = None
    active: bool | None = None


@app.get("/version", include_in_schema=False)
def get_version():
    from relaix.version import get_version as pkg_version

    return {"version": pkg_version()}


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index_ui():
    return HTMLResponse((_STATIC_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/rules-ui", response_class=HTMLResponse, include_in_schema=False)
def rules_ui():
    return HTMLResponse((_STATIC_DIR / "rules.html").read_text(encoding="utf-8"))


@app.get("/history-ui", response_class=HTMLResponse, include_in_schema=False)
def history_ui():
    return HTMLResponse((_STATIC_DIR / "history.html").read_text(encoding="utf-8"))


# ── sources ──────────────────────────────────────────────────────────────


@app.get("/sources", dependencies=[Depends(verify_token)])
def get_sources():
    return api.list_sources()


@app.post("/sources", dependencies=[Depends(verify_token)])
def post_source(req: SourceRequest):
    return api.create_source(**req.model_dump())


@app.get("/sources/{source_id}", dependencies=[Depends(verify_token)])
def get_source(source_id: str):
    source = api.get_source(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@app.patch("/sources/{source_id}", dependencies=[Depends(verify_token)])
def patch_source(source_id: str, req: SourceUpdateRequest):
    fields = {k: v for k, v in req.model_dump().items() if v is not None}
    updated = api.update_source(source_id, **fields)
    if updated is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return updated


@app.delete(
    "/sources/{source_id}", dependencies=[Depends(verify_token)], status_code=204
)
def delete_source(source_id: str):
    if not api.delete_source(source_id):
        raise HTTPException(status_code=404, detail="Source not found")
    return Response(status_code=204)


# ── rules ────────────────────────────────────────────────────────────────


@app.get("/rules", dependencies=[Depends(verify_token)])
def get_rules(source_id: str | None = None):
    rules = api.list_rules(source_id)
    return [
        {**vars(rule), "conditions": api.list_rule_conditions(rule.id)}
        for rule in rules
    ]


@app.post("/rules", dependencies=[Depends(verify_token)])
def post_rule(req: RuleRequest):
    try:
        rule = api.create_rule(
            req.name,
            req.source_id,
            req.action_url,
            req.action_token,
            [c.model_dump() for c in req.conditions],
        )
    except api.InvalidConditionError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return {**vars(rule), "conditions": api.list_rule_conditions(rule.id)}


@app.get("/rules/{rule_id}", dependencies=[Depends(verify_token)])
def get_rule(rule_id: str):
    rule = api.get_rule(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {**vars(rule), "conditions": api.list_rule_conditions(rule.id)}


@app.patch("/rules/{rule_id}", dependencies=[Depends(verify_token)])
def patch_rule(rule_id: str, req: RuleUpdateRequest):
    fields = {k: v for k, v in req.model_dump().items() if v is not None}
    updated = api.update_rule(rule_id, **fields)
    if updated is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {**vars(updated), "conditions": api.list_rule_conditions(updated.id)}


@app.put("/rules/{rule_id}/conditions", dependencies=[Depends(verify_token)])
def put_rule_conditions(rule_id: str, conditions: list[ConditionRequest]):
    if api.get_rule(rule_id) is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    try:
        return api.replace_rule_conditions(
            rule_id, [c.model_dump() for c in conditions]
        )
    except api.InvalidConditionError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.delete("/rules/{rule_id}", dependencies=[Depends(verify_token)], status_code=204)
def delete_rule(rule_id: str):
    if not api.delete_rule(rule_id):
        raise HTTPException(status_code=404, detail="Rule not found")
    return Response(status_code=204)


# ── events / polling log / rule executions ──────────────────────────────


@app.get("/events", dependencies=[Depends(verify_token)])
def get_events(
    source_id: str | None = None, status: str | None = None, limit: int = 100
):
    events = api.list_events(source_id=source_id, status=status, limit=limit)
    return [{**vars(e), "raw_payload": _try_parse_json(e.raw_payload)} for e in events]


@app.get("/events/{event_id}", dependencies=[Depends(verify_token)])
def get_event(event_id: str):
    event = api.get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    executions = api.list_rule_executions(event_id=event_id)
    return {
        **vars(event),
        "raw_payload": _try_parse_json(event.raw_payload),
        "rule_executions": executions,
    }


@app.post("/events/{event_id}/reset", dependencies=[Depends(verify_token)])
def post_reset_event(event_id: str):
    if not api.reset_event(event_id):
        raise HTTPException(
            status_code=409, detail="Event isn't in processing — nothing to reset"
        )
    return api.get_event(event_id)


@app.get("/rule-executions", dependencies=[Depends(verify_token)])
def get_rule_executions(
    event_id: str | None = None, rule_id: str | None = None, status: str | None = None
):
    return api.list_rule_executions(event_id=event_id, rule_id=rule_id, status=status)


@app.post("/rule-executions/{execution_id}/reset", dependencies=[Depends(verify_token)])
def post_reset_rule_execution(execution_id: str):
    if not api.reset_rule_execution(execution_id):
        raise HTTPException(
            status_code=409, detail="Execution isn't in processing — nothing to reset"
        )
    return {"id": execution_id, "status": "pending"}


@app.get("/polling-log", dependencies=[Depends(verify_token)])
def get_polling_log(source_id: str | None = None, limit: int = 100):
    return api.list_polling_log(source_id, limit)


def _try_parse_json(raw: str):
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return raw
