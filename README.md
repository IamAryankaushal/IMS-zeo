# Incident Management System (IMS)

A mission-critical, production-grade Incident Management System built to monitor a complex
distributed stack (APIs, MCP Hosts, Distributed Caches, Async Queues, RDBMS, and NoSQL stores)
and manage failure mediation workflows from signal ingestion to root cause analysis.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Tech Stack & Design Decisions](#tech-stack--design-decisions)
3. [Project Structure](#project-structure)
4. [How Every Requirement Is Implemented](#how-every-requirement-is-implemented)
5. [Design Patterns](#design-patterns)
6. [Data Architecture](#data-architecture)
7. [Backpressure & Resilience](#backpressure--resilience)
8. [Observability](#observability)
9. [Security](#security)
10. [Setup & Running](#setup--running)
11. [Testing](#testing)
12. [Sample Failure Simulation](#sample-failure-simulation)
13. [API Reference](#api-reference)
14. [Tools & Prompts Used](#tools--prompts-used)

---

## Architecture Overview

```
                        ┌─────────────────────────────────────┐
                        │           INGESTION LAYER            │
                        │                                      │
              ┌─────────┤  HTTP POST /signals/ingest           │
              │         │  HTTP POST /signals/ingest/batch     │
              │         │  WebSocket /signals/ws               │
              │         └──────────────┬──────────────────────┘
              │                        │
              │                        ▼
              │         ┌─────────────────────────────────────┐
              │         │         RATE LIMITER                 │
              │         │     Token Bucket (10,000/sec)        │
              │         └──────────────┬──────────────────────┘
              │                        │ allowed
              │                        ▼
              │         ┌─────────────────────────────────────┐
              │         │      IN-MEMORY ASYNC QUEUE           │
              │         │   asyncio.Queue (max 50,000 items)   │◄── backpressure
              │         └──────────────┬──────────────────────┘
              │                        │
              │                        ▼
              │         ┌─────────────────────────────────────┐
              │         │       BACKGROUND WORKER              │
              │         │   concurrency=20 (semaphore)         │
              │         │   retry logic (3x exponential)       │
              │         └──────┬───────┬───────┬──────────────┘
              │                │       │       │
              │                ▼       ▼       ▼
              │    ┌─────────────┐ ┌───────┐ ┌──────────────┐
              │    │  DEBOUNCE   │ │ALERT  │ │    STATE     │
              │    │  ENGINE     │ │STRAT. │ │   MACHINE    │
              │    │ 100/10s     │ │PATTERN│ │OPEN→CLOSED   │
              │    └──────┬──────┘ └───┬───┘ └──────┬───────┘
              │           │            │             │
              ▼           ▼            ▼             ▼
┌─────────────────────────────────────────────────────────────────┐
│                        STORAGE LAYER                             │
│                                                                  │
│  ┌─────────────┐  ┌──────────────┐  ┌────────┐  ┌───────────┐  │
│  │  MongoDB    │  │  PostgreSQL  │  │ Redis  │  │Timescale  │  │
│  │  Raw Signal │  │  Work Items  │  │  Hot   │  │  DB       │  │
│  │  Audit Log  │  │  RCA Records │  │ Cache  │  │Time-series│  │
│  └─────────────┘  └──────────────┘  └────────┘  └───────────┘  │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FASTAPI BACKEND                             │
│   /signals/ingest   /workitems   /rca   /health                 │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                     REACT FRONTEND (Nginx)                       │
│   Dashboard │ Incident Detail │ RCA Form │ Test Ingest          │
└─────────────────────────────────────────────────────────────────┘
```

### Incident Lifecycle Flow

```
Signal arrives at API
        │
        ▼
Rate Limiter (token bucket)
        │ rejected → 429 Too Many Requests
        ▼ allowed
asyncio.Queue.put_nowait()     ← non-blocking, returns HTTP 202 immediately
        │ full → drop + warn (no crash)
        ▼
Background worker picks up signal
        │
        ├── 1. MongoDB insert (raw audit log, every signal stored)
        │
        ├── 2. Debounce check
        │       < 100 signals in 10s for same component → update signal count only
        │      >= 100 signals in 10s → create exactly 1 Work Item
        │
        ├── 3. PostgreSQL transaction
        │       existing OPEN/INVESTIGATING work item? → increment signal_count
        │       no work item? → resolve_strategy() → P0/P1/P2/P3 → create WorkItem
        │
        ├── 4. MongoDB update: link signal_id → work_item_id
        │
        └── 5. Redis invalidate: bust dashboard cache keys

State Transition (user-triggered via UI):
        OPEN → INVESTIGATING → RESOLVED → CLOSED
                                               │
                                        requires RCA
                                        auto-calculates MTTR
```

---

## Tech Stack & Design Decisions

| Layer | Technology | Why |
|---|---|---|
| Backend Framework | FastAPI | Async-native, automatic OpenAPI docs, Pydantic integration |
| Primary DB | PostgreSQL + TimescaleDB | ACID transactions for work items; TimescaleDB for time-series signal aggregations |
| Document Store | MongoDB (motor) | Schema-flexible, high write throughput for raw signal payloads |
| Cache | Redis | Sub-millisecond hot-path reads for dashboard; pub/sub ready |
| Queue | asyncio.Queue | In-process, zero-latency, provides backpressure without external dependency |
| ORM | SQLAlchemy (async) | Type-safe, connection pooling, async session management |
| Frontend | React + Vite + TailwindCSS | Fast build, component-based, utility-first styling |
| Reverse Proxy | Nginx | Serves static frontend, proxies /api → backend |
| Containerisation | Docker + Docker Compose | Single-command reproducible environment |
| Testing | pytest + pytest-asyncio | Async test support, clean fixture model |

---

## Project Structure

```
IMS/
├── docker-compose.yml               # Orchestrates all 5 services
├── scripts/
│   ├── init_postgres.sql            # Schema + TimescaleDB hypertable setup
│   ├── simulate_failure.py          # Failure simulation script
│   └── sample_signals.json          # Sample signal payloads
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── pyproject.toml               # pytest config
│   ├── tests/
│   │   └── test_core.py             # 29 unit tests
│   └── app/
│       ├── main.py                  # FastAPI app, startup/shutdown lifecycle
│       ├── core/
│       │   ├── config.py            # Pydantic settings from env vars
│       │   ├── rate_limiter.py      # Token bucket rate limiter
│       │   ├── queue.py             # In-memory bounded async queue
│       │   ├── alert_strategy.py    # Strategy pattern for P0/P1/P2/P3
│       │   └── state_machine.py     # State pattern for OPEN→CLOSED
│       ├── db/
│       │   └── connections.py       # Postgres + MongoDB + Redis clients
│       ├── models/
│       │   ├── orm.py               # SQLAlchemy ORM models
│       │   └── schemas.py           # Pydantic request/response schemas
│       ├── api/
│       │   ├── signals.py           # Ingestion endpoints + WebSocket
│       │   ├── workitems.py         # Work item CRUD + transitions
│       │   ├── rca.py               # RCA submission + retrieval
│       │   └── health.py            # /health endpoint
│       ├── services/
│       │   └── signal_service.py    # Debounce engine + work item logic
│       └── workers/
│           └── signal_worker.py     # Background queue consumer
└── frontend/
    ├── Dockerfile
    ├── nginx.conf
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── App.jsx                  # Router + health polling
        ├── api/client.js            # Axios API client
        ├── components/
        │   ├── Navbar.jsx
        │   └── Badges.jsx           # Priority + Status chips
        └── pages/
            ├── Dashboard.jsx        # Live incident feed
            ├── IncidentDetail.jsx   # Signals + state transitions
            ├── RCAForm.jsx          # RCA submission form
            └── IngestTest.jsx       # Signal injection testing UI
```

---

## How Every Requirement Is Implemented

### A. Ingestion & In-Memory Processing

**Signal Ingestion — Multiple Protocols**

Three ingestion paths are supported:

- `POST /signals/ingest` — single signal over HTTP REST
- `POST /signals/ingest/batch` — up to 1000 signals per request
- `WebSocket /signals/ws` — persistent connection for high-throughput streaming

All three paths go through the same rate limiter and queue, ensuring consistent
backpressure behaviour regardless of protocol.

**Memory Management — 10,000 signals/sec burst handling**

The system uses a bounded `asyncio.Queue` with a maximum size of 50,000 items.
The ingestion API layer is completely decoupled from the persistence layer:

```
HTTP request → rate check → queue.put_nowait() → return 202
                                    ↓
                          (background worker drains queue)
```

`put_nowait()` is non-blocking. If the queue is full, the signal is dropped with
a warning log rather than blocking the API or crashing. This means the ingestion
layer can always accept requests even if Postgres or MongoDB are slow.

**Debounce Logic — 100 signals / 10 seconds → 1 Work Item**

The `DebounceWindow` class in `signal_service.py` maintains a rolling time window
per component ID. It uses an `asyncio.Lock` to prevent race conditions:

```python
# 100 signals for CACHE_CLUSTER_01 within 10 seconds
# → exactly 1 Work Item created
# → all 100 signals stored in MongoDB and linked to that Work Item
```

The debounce fires exactly once when the count crosses 100 — not on every
subsequent signal. All signals are still stored in MongoDB regardless.

---

### B. Distribution & Persistence

**MongoDB — Raw Signal Audit Log (The Data Lake)**

Every signal that passes the rate limiter is stored in MongoDB with full payload:
component ID, error type, message, latency, metadata, and timestamp. After a
Work Item is created, the signal document is updated with its `work_item_id`
so all signals for an incident can be queried together.

MongoDB was chosen here because:
- Schema-flexible (different component types have different metadata shapes)
- High write throughput for burst ingestion
- No transaction overhead needed for append-only audit log

**PostgreSQL + TimescaleDB — Source of Truth**

Work Items and RCA Records are stored in PostgreSQL with full ACID guarantees.
State transitions (OPEN → INVESTIGATING → RESOLVED → CLOSED) are wrapped in
database transactions — partial updates are impossible.

TimescaleDB extension is enabled and `signal_metrics` is converted to a
hypertable for efficient time-series aggregation queries:

```sql
SELECT create_hypertable('signal_metrics', 'time', if_not_exists => TRUE);
```

**Redis — Hot-Path Dashboard Cache**

To avoid hitting Postgres on every dashboard refresh (which auto-refreshes every
5 seconds), the `/workitems` list response is cached in Redis with a 30-second TTL.
Individual work item responses are also cached under `ims:workitem:{id}`.

Cache is invalidated whenever a work item is created, updated, or transitions state.

**TimescaleDB — Time-Series Aggregations**

The `signal_metrics` table is a TimescaleDB hypertable partitioned by time. This
allows efficient queries like "signals per component per minute" without full table
scans, even at high data volumes.

---

### C. The Workflow Engine

**Alerting Strategy — Strategy Design Pattern**

Different component failures trigger different alert priorities. This is implemented
using the Strategy pattern — each component type has its own strategy class:

```
RDBMS / POSTGRES / DB   →  RDBMSFailureStrategy  →  P0 (critical)
KAFKA / QUEUE / RABBIT  →  QueueFailureStrategy   →  P1 (high)
API / MCP / SERVICE     →  APIFailureStrategy     →  P1 (high)
CACHE / REDIS           →  CacheFailureStrategy   →  P2 (medium)
everything else         →  DefaultFailureStrategy →  P3 (low)
```

The `resolve_strategy(component_id)` function inspects the component ID prefix
(e.g. `CACHE_CLUSTER_01` → `CacheFailureStrategy`). Adding a new component type
requires only a new class and one line in the registry — no existing code changes.

**Work Item State Machine — State Design Pattern**

Each status is its own class that knows its valid transitions:

```
OpenState          → allowed: [INVESTIGATING]
InvestigatingState → allowed: [RESOLVED, OPEN]
ResolvedState      → allowed: [CLOSED, INVESTIGATING]
ClosedState        → allowed: [] (terminal)
```

Attempting `OPEN → CLOSED` raises a `ValueError` with a clear message before
any database write happens. The API layer catches this and returns a 400.

An additional guard sits at the API level: transitioning to `CLOSED` is rejected
with a 422 if no RCA record exists for the work item.

---

### Functional Requirements

**Async Processing**

The entire backend is async — FastAPI, SQLAlchemy (asyncpg driver), motor (MongoDB),
redis.asyncio, and the background worker all use `async/await`. No thread blocking
anywhere in the hot path.

**Mandatory RCA**

Two layers of enforcement:

1. API guard in `transition_work_item`: if `target == CLOSED` and `item.rca is None`
   → raises HTTP 422 with message "Cannot close work item without a complete RCA"

2. RCA schema validation via Pydantic:
   - `incident_end` must be after `incident_start`
   - `root_cause_description`, `fix_applied`, `prevention_steps` must be ≥ 10 characters
   - `root_cause_category` must be one of 8 allowed values

**MTTR Calculation**

MTTR (Mean Time To Repair) is calculated automatically in two places:

- When RCA is submitted: `mttr = incident_end - incident_start` (in seconds)
- When work item is CLOSED: `mttr = closed_at - first_signal_at` (in seconds)

Displayed in the UI as minutes (e.g. `47m`).

---

## Design Patterns

### 1. Strategy Pattern — Alert Routing

```
           AlertStrategy (abstract)
                   │
      ┌────────────┼────────────┬──────────────┐
      ▼            ▼            ▼              ▼
 RDBMSFailure  CacheFailure  QueueFailure  APIFailure
 Strategy      Strategy      Strategy      Strategy
 (P0)          (P2)          (P1)          (P1)
```

Each strategy implements `get_priority()`, `get_title()`, and `notify()`.
The `resolve_strategy()` factory picks the right one at runtime based on
the component ID — the caller never needs to know which strategy was chosen.

### 2. State Pattern — Incident Lifecycle

```
  ┌──────┐    ┌───────────────┐    ┌──────────┐    ┌────────┐
  │ OPEN │───►│ INVESTIGATING │───►│ RESOLVED │───►│ CLOSED │
  └──────┘    └───────────────┘    └──────────┘    └────────┘
                      │                  │
                      ▼                  ▼
                   ┌──────┐      ┌───────────────┐
                   │ OPEN │      │ INVESTIGATING │
                   └──────┘      └───────────────┘
```

Each state is a class. Invalid transitions raise errors before touching the DB.
`CLOSED` is a terminal state with no outgoing transitions.

### 3. Producer-Consumer Pattern — Queue Worker

```
  Ingestion API (Producer)          Background Worker (Consumer)
  ┌─────────────────────┐           ┌────────────────────────┐
  │ POST /signals/ingest│──────────►│ asyncio.Queue          │
  │ WebSocket /ws       │  put_     │ (bounded, 50k max)     │
  │ POST /batch         │  nowait() │                        │
  └─────────────────────┘           │ Semaphore(20)          │
                                    │ → MongoDB write        │
                                    │ → Debounce check       │
                                    │ → Postgres transaction │
                                    │ → Redis invalidate     │
                                    └────────────────────────┘
```

---

## Data Architecture

### PostgreSQL Schema

```sql
work_items
├── id UUID PRIMARY KEY
├── component_id VARCHAR(100)
├── title VARCHAR(500)
├── status VARCHAR(20)          -- OPEN|INVESTIGATING|RESOLVED|CLOSED
├── priority VARCHAR(5)         -- P0|P1|P2|P3
├── signal_count INTEGER
├── first_signal_at TIMESTAMPTZ
├── last_signal_at TIMESTAMPTZ
├── resolved_at TIMESTAMPTZ
├── closed_at TIMESTAMPTZ
├── mttr_seconds INTEGER
├── created_at TIMESTAMPTZ
└── updated_at TIMESTAMPTZ

rca_records
├── id UUID PRIMARY KEY
├── work_item_id UUID → work_items(id)  -- 1:1, CASCADE DELETE
├── incident_start TIMESTAMPTZ
├── incident_end TIMESTAMPTZ
├── root_cause_category VARCHAR(50)
├── root_cause_description TEXT
├── fix_applied TEXT
├── prevention_steps TEXT
├── submitted_by VARCHAR(100)
└── submitted_at TIMESTAMPTZ

signal_metrics (TimescaleDB hypertable, partitioned by time)
├── time TIMESTAMPTZ
├── component_id VARCHAR(100)
├── signal_count INTEGER
├── error_rate FLOAT
├── avg_latency_ms FLOAT
└── p99_latency_ms FLOAT
```

### MongoDB Document Shape

```json
{
  "_id": "ObjectId(...)",
  "signal_id": "uuid",
  "component_id": "CACHE_CLUSTER_01",
  "component_type": "CACHE",
  "error_type": "CACHE_MISS_STORM",
  "message": "Redis cluster miss rate exceeded 90%",
  "latency_ms": 850.4,
  "metadata": { "hit_rate": 0.08 },
  "timestamp": "2026-05-03T10:32:13Z",
  "work_item_id": "uuid (set after debounce)",
  "_inserted_at": "2026-05-03T10:32:13Z"
}
```

### Redis Key Structure

```
ims:dashboard:active          → cached WorkItemListResponse (TTL 30s)
ims:workitem:{uuid}           → cached WorkItemResponse (TTL 30s)
```

---

## Backpressure & Resilience

### How Backpressure Is Handled

This is the most critical resilience property of the system. The requirement
states: *"your system cannot crash if persistence layer is slow."*

The solution uses a three-layer backpressure model:

**Layer 1 — Rate Limiter (Token Bucket)**

Before a signal even enters the system, it must acquire a token from the bucket.
The bucket refills at 10,000 tokens/second. If the bucket is empty (burst
exceeding sustained rate), the request gets a `429` immediately — no work done.

```python
# Token bucket: capacity=10000, refill_rate=10000/sec
allowed = await limiter.consume(1)
if not allowed:
    return 429 Too Many Requests
```

**Layer 2 — Bounded In-Memory Queue**

Signals that pass the rate limiter are placed into a bounded `asyncio.Queue`
(max 50,000 items) using `put_nowait()` — which never blocks. The HTTP handler
returns `202 Accepted` immediately after enqueuing, regardless of how busy the
databases are. If the queue is full, the signal is dropped with a warning rather
than blocking the API thread.

```
DB slow → queue fills up → put_nowait() returns False → signal dropped
                                                       → API still responds 202
                                                       → system does NOT crash
```

**Layer 3 — Worker Semaphore**

The background worker uses `asyncio.Semaphore(20)` to bound concurrent database
operations. This prevents connection pool exhaustion even if the queue drains
faster than the DB can handle.

### Retry Logic

Every signal processing attempt has 3 retries with exponential backoff:
- Attempt 1 fails → wait 0.1s → retry
- Attempt 2 fails → wait 0.2s → retry
- Attempt 3 fails → log error, discard signal

```python
for attempt in range(3):
    try:
        await process_signal(signal)
        return
    except Exception:
        await asyncio.sleep(0.1 * (2 ** attempt))
```

### Other Resilience Features

- **Connection pool pre-ping** — SQLAlchemy pings Postgres before using a
  connection, detecting stale connections automatically
- **Health checks on all Docker services** — dependent services wait for
  their dependencies to be healthy before starting
- **DB-level constraints** — `CHECK` constraints on status and priority columns
  provide a safety net beyond application-level validation
- **Cascade deletes** — deleting a Work Item automatically removes its RCA record

---

## Observability

### /health Endpoint

```json
GET /health

{
  "status": "healthy",
  "environment": "production",
  "queue_size": 142,
  "queue_capacity": 50000,
  "services": {
    "postgres": "ok",
    "mongodb": "ok",
    "redis": "ok"
  }
}
```

Returns `"degraded"` if any service fails its ping. Checked by Docker's
HEALTHCHECK every 10 seconds.

### Throughput Metrics

Every 5 seconds the worker prints to console:

```
📊 METRICS | processed=1247 | rate=249.4 sig/s | queue=18/50000 | dropped=0
```

Fields: total signals processed, current rate (signals/sec), queue depth,
signals dropped due to full queue.

---

## Security

The following security measures are implemented as bonus items:

**Rate Limiting** — Token bucket at the ingestion layer prevents DoS via
signal flooding. Sustained rate of 10,000 signals/sec is enforced.

**Input Validation** — All inputs are validated by Pydantic v2 schemas before
any database operation. Invalid payloads are rejected with descriptive 422 errors.

**DB-Level Constraints** — PostgreSQL CHECK constraints on `status` and `priority`
columns ensure data integrity even if application validation is bypassed.

**CORS Middleware** — FastAPI CORS middleware is configured. In production,
`allow_origins` should be restricted to the frontend domain.

**SQL Injection Prevention** — All database queries use SQLAlchemy ORM with
parameterised queries — no raw SQL string interpolation anywhere.

**No Secrets in Code** — All credentials (DB passwords, connection strings) are
passed via environment variables defined in `docker-compose.yml`, never hardcoded.

---

## Setup & Running

### Prerequisites

- Docker Desktop (includes Docker Compose)
- Python 3.11+ (only for running tests locally)
- Git

### Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/IMS.git
cd IMS

# 2. Start all services
docker compose up --build

# 3. Wait for this line in the logs:
#    backend-1 | Signal worker task scheduled

# 4. Open the dashboard
open http://localhost:3000

# 5. Inject sample failures
python3 scripts/simulate_failure.py --burst
```

### Service URLs

| Service | URL |
|---|---|
| React Dashboard | http://localhost:3000 |
| FastAPI Backend | http://localhost:8000 |
| Swagger API Docs | http://localhost:8000/docs |
| Health Endpoint | http://localhost:8000/health |
| PostgreSQL | localhost:5432 |
| MongoDB | localhost:27017 |
| Redis | localhost:6379 |

### Environment Variables

All configurable via `docker-compose.yml` environment section:

| Variable | Default | Description |
|---|---|---|
| DATABASE_URL | postgresql+asyncpg://... | PostgreSQL connection string |
| MONGODB_URL | mongodb://... | MongoDB connection string |
| REDIS_URL | redis://redis:6379/0 | Redis connection string |
| QUEUE_MAX_SIZE | 50000 | In-memory queue capacity |
| RATE_LIMIT_PER_SECOND | 10000 | Token bucket refill rate |
| DEBOUNCE_WINDOW_SECONDS | 10 | Debounce time window |
| DEBOUNCE_THRESHOLD | 100 | Signals per window to trigger debounce |
| METRICS_INTERVAL_SECONDS | 5 | Console metrics print interval |

### Useful Commands

```bash
# Start in background
docker compose up -d --build

# View backend logs (includes metrics)
docker compose logs -f backend

# Stop everything
docker compose down

# Wipe all data and start fresh
docker compose down -v && docker compose up --build

# Restart backend after code change
docker compose up --build backend -d
```

---

## Testing

29 unit tests covering all core business logic. No database required — all tests
run against pure Python classes.

```bash
cd backend
pip install pytest pytest-asyncio anyio --break-system-packages
python3 -m pytest tests/test_core.py -v
```

### Test Coverage

| Suite | Tests | What Is Covered |
|---|---|---|
| TestStateMachine | 9 | All valid transitions, all invalid transitions, terminal state, full lifecycle |
| TestRCAValidation | 8 | Valid RCA, end before start, equal timestamps, short fields, invalid category, all 8 valid categories |
| TestAlertStrategy | 9 | P0 for RDBMS/Postgres, P1 for Queue/API/MCP, P2 for Cache/Redis, P3 for unknown, title format |
| TestRateLimiter | 3 | Allows within capacity, blocks when exhausted, refills over time |

### Example Output

```
tests/test_core.py::TestStateMachine::test_open_to_investigating     PASSED
tests/test_core.py::TestStateMachine::test_invalid_open_to_closed    PASSED
tests/test_core.py::TestRCAValidation::test_valid_rca_passes         PASSED
tests/test_core.py::TestRCAValidation::test_end_before_start_fails   PASSED
tests/test_core.py::TestAlertStrategy::test_rdbms_is_p0             PASSED
tests/test_core.py::TestRateLimiter::test_blocks_when_full           PASSED
...
29 passed in 0.12s
```

---

## Sample Failure Simulation

### simulate_failure.py

Simulates a realistic multi-component outage scenario:

```
Phase 1 — RDBMS outage
  → 110 signals to RDBMS_PRIMARY_01
  → triggers debounce (>100 in 10s)
  → 1 P0 Work Item created, all signals linked

Phase 2 — Cache degradation
  → 15 signals to CACHE_CLUSTER_01
  → 1 P2 Work Item created

Phase 3 — MCP host failure
  → 8 signals to MCP_HOST_PROD
  → 1 P1 Work Item created

Phase 4 — Kafka queue backup
  → 1 signal to KAFKA_BROKER_01
  → 1 P1 Work Item created
```

```bash
# Normal run (5 signals per component)
python3 scripts/simulate_failure.py

# Burst run (110 signals to trigger debounce)
python3 scripts/simulate_failure.py --burst
```

---

## API Reference

### Signal Ingestion

```
POST   /signals/ingest          Ingest a single signal
POST   /signals/ingest/batch    Ingest up to 1000 signals
WS     /signals/ws              WebSocket stream ingestion
```

### Work Items

```
GET    /workitems                List all work items (filterable, cached)
GET    /workitems/{id}           Get single work item (cached)
PATCH  /workitems/{id}/transition Transition status (state machine enforced)
GET    /workitems/{id}/signals   Get raw signals from MongoDB
```

### RCA

```
POST   /rca/{work_item_id}      Submit RCA (validates all fields)
GET    /rca/{work_item_id}      Retrieve existing RCA
```

### System

```
GET    /health                  System health + queue status
GET    /docs                    Swagger interactive API documentation
```

---

## Tools & Prompts Used

This project was built with the assistance of Claude (Anthropic) as an
AI pair-programming tool, as permitted by the assignment guidelines
("open-book test, free to use any GPT tool of your choice").

Claude was used for:
- System architecture design and tech stack selection
- Generating boilerplate for FastAPI, SQLAlchemy, motor, and Redis async clients
- Implementing the Strategy and State design patterns
- Writing the unit test suite
- Debugging dependency version conflicts (motor/pymongo compatibility)
- Assisting with this README
