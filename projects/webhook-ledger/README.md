# Webhook Ledger

A Django backend demonstrating reliable payment webhook ingestion and database processing. Built as an independent portfolio project using synthetic events, inspired by backend integration problems such as repeated deliveries and transient failures.

## Features implemented

- HMAC-SHA256 signatures over the exact timestamp and request body; constant-time signature comparison.
- Five-minute timestamp tolerance and a 64 KiB payload limit.
- Request validation and unique event IDs; conflicting reuse returns HTTP 409.
- Durable database inbox: HTTP 202 means persisted, not necessarily processed.
- Payment IDs prevent repeated ledger entries, even across different event IDs.
- Database transactions and handler savepoints roll back partial writes.
- Background management command, exponential retry delay, and dead-letter status after five attempts.
- Paginated event monitoring restricted to staff users.
- SQLite quick start, PostgreSQL Docker setup, migrations, and GitHub Actions configuration.

## Quick start: Python 3.12+

```bash
cd projects/webhook-ledger
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
set -a
source .env
set +a
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

In a second terminal, activate the same virtual environment and load `.env`, then run:

```bash
python manage.py process_events
```

In a third terminal with the same environment:

```bash
python scripts/send_demo.py
python scripts/send_demo.py
```

The second delivery returns `duplicate: true`. The worker records one payment. To inspect events, use a staff user's credentials:

```bash
curl --user YOUR_USERNAME http://127.0.0.1:8000/api/events/
```

Curl prompts for your password. Use HTTPS for Basic authentication outside a local demo.

## PostgreSQL with Docker

```bash
cp .env.example .env
docker compose up -d db
docker compose run --rm api python manage.py migrate
docker compose run --rm api python manage.py createsuperuser
docker compose up --build -d api worker
```

The API is bound to localhost. Replace demo secrets before deployment. The provided compose file is for local development.

## Event contract

POST `/api/webhooks/` with `Content-Type: application/json`:

```json
{
  "event_id": "evt_demo_1",
  "type": "payment.captured",
  "data": {
    "payment_id": "pay_demo_1",
    "amount_minor": 149900,
    "currency": "INR"
  }
}
```

`amount_minor` is a positive integer in minor currency units. Currency is an uppercase three-letter code; this demo validates its shape rather than consulting an ISO currency registry.

Headers:

- `X-Webhook-Timestamp`: Unix timestamp in seconds.
- `X-Webhook-Signature`: hex HMAC-SHA256 using `WEBHOOK_SECRET` over `timestamp + "." + raw_body`.

This is a custom demonstration contract, not a Razorpay-compatible webhook endpoint.

| Endpoint | Access | Purpose |
| --- | --- | --- |
| GET /health/ | Public | Process liveness; does not test database readiness |
| POST /api/webhooks/ | Signature | Persist a validated event |
| GET /api/events/?status=retry | Staff Basic auth | Paginated monitoring without raw payment payloads |

## Processing design

The database acts as a durable inbox, so acceptance does not depend on publishing to a separate queue. Workers fetch due events, lock each event, and commit the ledger write and event state together. A worker crash before commit leaves the event available for another attempt.

Retry delays are 2, 4, 8, and 16 seconds; a fifth failed attempt marks the event `dead`. Conflicting payment data is a permanent failure and goes directly to `dead`. A repeated payment with matching amount and currency is treated as successful without inserting another payment.

PostgreSQL is required for concurrent worker row locking. SQLite is a single-worker convenience mode: Django's `select_for_update()` has no effect on SQLite. See the [Django documentation](https://docs.djangoproject.com/en/5.2/ref/models/querysets/#select-for-update).

## Validation

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

Tests cover signed ingestion, invalid/stale signatures, duplicate delivery, ID conflicts, schema validation, permission checks, retry recovery, retry exhaustion, and partial-write rollback. CI runs the suite against SQLite and PostgreSQL. Local validation results are recorded in `VALIDATION.md`.

## Scope and next steps

This is a portfolio demonstration, not a deployed payment service. It does not initiate payments or call external APIs. Its idempotency guarantee applies to local ledger writes, not arbitrary external side effects. The worker has no dead-letter replay endpoint, per-tenant secret rotation, rate limiting, metrics exporter, or production deployment configuration. The local tests do not prove concurrency behavior or load capacity.

Good extensions: PostgreSQL concurrency tests, replay with audit history, tenant-specific signing secrets, structured metrics, and an outbox for downstream notifications.

## Interview discussion

- Why persist the event before returning HTTP 202?
- How do event-level and payment-level idempotency differ?
- What happens if a process crashes after receiving an event?
- How would an outbox make downstream notification delivery reliable?
- Which guarantees change when a handler calls an external service?
