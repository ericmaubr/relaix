# relaix

A small, generic service for turning webhooks you can't receive directly
into HTTP calls you can act on.

## Why

Some environments can't expose an inbound endpoint to the internet (no open
port, no public IP, restrictive network policy) but *can* make outbound
HTTPS calls. `relaix` bridges that gap: it periodically **pulls** events from
a buffer provider (e.g. [webhook.site](https://webhook.site)) instead of
waiting for a push, matches each event against rules you define, and — when
a rule matches — makes an HTTP call to a destination URL of your choosing
with the event's payload.

It doesn't know anything about the shape of any particular webhook. It
only understands: *fetch events from a source, evaluate rules against a
JSON payload, POST to a URL when a rule matches.* Whatever the payload means
is up to the destination endpoint.

## Concepts

- **Source** (`webhook_source`) — a channel to poll for new events (a
  webhook.site token, for now — the `kind` column leaves room for other
  providers later).
- **Event** (`webhook_event`) — one raw payload pulled from a source. Stored
  as soon as it's fetched, before any rule evaluation, so the data survives
  regardless of what happens downstream.
- **Rule** (`webhook_rule` + `webhook_rule_condition`) — a set of conditions
  against fields in the event payload (dotted path, e.g. `message.name`) and
  an action: an HTTP endpoint to call when all conditions in a group match.
- **Rule execution** (`webhook_rule_execution`) — one row per (event × rule
  that matched it), tracking whether the action call succeeded.
- **Polling log** (`webhook_polling_log`) — one row per polling cycle, for
  debugging "did we actually check the source" independently of whether any
  event was found.

See [`src/relaix/db.py`](src/relaix/db.py) for the full schema.

## Condition operators

| Operator | Meaning |
|---|---|
| `=` | equals |
| `!=` (or `<>`, normalized to `!=`) | not equal |
| `contains` | substring match |
| `not_contains` | negated substring match |
| `>`, `>=`, `<`, `<=` | comparison — tries numeric comparison first, falls back to string comparison (works for ISO 8601 dates by construction) |

Conditions in the same `group_index` are combined with AND. OR-across-groups
is modeled in the schema but not evaluated yet (see "Out of scope" below).

## Architecture notes

- **Pull, not push.** `relaix` never needs an inbound port. It calls out to
  the source provider's API on a schedule.
- **Collector and Executor are decoupled.** Fetching new events and
  evaluating/dispatching rules are two independent processes with their own
  retry policies — an event is fetched once, but rule evaluation against it
  can be retried independently.
- **No external message queue.** At the expected volume (a handful of events
  a day, not per second), a dedicated queue would be disproportionate
  complexity. "Don't process the same item twice concurrently" is guaranteed
  by an atomic conditional `UPDATE` claim on the row, not a distributed lock.
- **No automatic reaper.** A rule execution stuck in `processing` (e.g. the
  process died mid-dispatch) is surfaced in the UI with a visual highlight
  and a manual "reset to pending" action, not corrected by a background
  timeout policy.

## Status

Schema, HTTP API (sources/rules CRUD, read-only events/executions/polling
log), CLI (`serve`, `migrate`, `provision-db`) are in place. The Collector
(polling job) and Executor (rule evaluation + dispatch job) are not
implemented yet — see "Implementation order" below.

## Implementation order

1. ~~Repo scaffold (FastAPI + SQLAlchemy Core + Alembic).~~
2. ~~Full data model + initial migration.~~
3. Collector: polling job for `webhook_site`-kind sources, writing
   `webhook_event` and `webhook_polling_log`.
4. Rule engine + Executor: condition evaluation, atomic claim,
   `webhook_rule_execution`, action HTTP dispatch.
5. UI: Sources → Rules → History (AG Grid, same visual pattern used
   elsewhere — history depends on there being real data to show).
6. Deploy as a background service (Collector + Executor loops + local UI —
   no public inbound port needed).

## Running locally

```bash
pip install -e ".[dev]"
python -m relaix migrate      # applies the schema (SQLite by default)
python -m relaix serve        # starts the HTTP API on 127.0.0.1:8790
```

Copy [`example-api.conf`](example-api.conf) to `api.conf` to configure host,
port, bearer token and database URL instead of passing flags/env vars.

## Out of scope (for now)

- Source providers other than webhook.site (the `kind` column leaves the
  door open, not implemented until there's a real need).
- OR-across-groups in rule conditions (column exists, evaluation of multiple
  groups isn't implemented until there's a real need).
- Automatic reaper for stuck `processing` rows — handled via the UI for now.
- External message queue — revisit only if volume grows by orders of
  magnitude.

## License

MIT — see [LICENSE](LICENSE).
