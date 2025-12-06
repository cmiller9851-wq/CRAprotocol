**README.md**

```markdown
# Containment Reflexion Audit (CRA Protocol)

**Version:** 1.2.0 (December 2025)  
**License:** Apache 2.0  

Containment Reflexion Audit (CRA) hashes build artifacts, stores them in PostgreSQL, scores them with a configurable metric, and automatically enforces actions (Arweave pinning or webhook alerts) via a BullMQ worker, ensuring tamper‑evident provenance and hands‑free remediation for CI/CD pipelines.

---

## Table of Contents
1. [Project Overview](#project-overview)  
2. [Architecture Diagram](#architecture-diagram)  
3. [Directory Layout](#directory-layout)  
4. [Prerequisites](#prerequisites)  
5. [Setup & Installation](#setup--installation)  
6. [Database Migrations](#database-migrations)  
7. [Running the Stack](#running-the-stack)  
8. [API Endpoints](#api-endpoints)  
9. [Enforcement Worker](#enforcement-worker)  
10. [Python Sweeper / Scorecard](#python-sweeper--scorecard)  
11. [Environment Variables](#environment-variables)  
12. [Testing the Flow](#testing-the-flow)  
13. [Troubleshooting](#troubleshooting)  
14. [Contributing](#contributing)  
15. [License](#license)  

---

## Project Overview
CRA provides a privacy‑focused, end‑to‑end solution for verifying artifact integrity, scoring them against quality metrics, and automatically enforcing corrective actions. It combines PostgreSQL for immutable state, Redis + BullMQ for reliable job processing, and optional Arweave pinning to guarantee tamper‑evident provenance.

---

## Architecture Diagram
```
+----------------+      +----------------+      +-------------------+
|  Node API      | ---> |  PostgreSQL DB | <--- |  Python Sweeper   |
| (Express)      |      | (artifacts,    |      | (Scorecard)       |
|                |      |  enforcements) |      |                   |
+----------------+      +----------------+      +-------------------+
        |                     ^                     |
        |                     |                     |
        v                     |                     v
   +-----------+   BullMQ   |               +-----------+
   |  Redis    |<----------+-------------->|  Worker   |
   +-----------+   Queue    |   (Arweave /   +-----------+
                                 Webhook)
```

---

## Directory Layout
```
├── docker-compose.yml
├── Dockerfile.node          # Node API + optional worker
├── Dockerfile.python        # Python sweeper
├── init.sql                 # Optional DB init script
├── k8s/                     # Kubernetes manifests (optional)
├── node/
│   ├── src/
│   │   ├── api/            # Express routes
│   │   ├── enforcement/
│   │   │   ├── router.ts   # Enqueue jobs
│   │   │   └── worker.ts   # BullMQ worker
│   │   ├── db/
│   │   │   ├── connection.ts
│   │   │   └── migrations/
│   │   │       └── 20251206_cra_beefed_schema.js
│   │   └── …
│   ├── package.json
│   └── tsconfig.json
├── python/
│   ├── main.py             # Sweep cron entrypoint
│   ├── scorecard.py        # Scoring logic
│   └── requirements.txt
└── README.md               # ← this file
```

---

## Prerequisites
- Docker ≥ 24 and docker‑compose  
- Node ≥ 20 (for local development)  
- Python ≥ 3.10 (for local development)  
- Git  

---

## Setup & Installation
```bash
# 1️⃣ Clone the repository
git clone https://github.com/cmiller9851-wq/CRAprotocol.git
cd CRAprotocol

# 2️⃣ Run the setup script (creates dirs, installs deps, builds containers)
chmod +x setup.sh
./setup.sh
```

The script will:

1. Create required directories.  
2. Install Node (`npm install`) and Python (`pip install -r python/requirements.txt`) dependencies.  
3. Build Docker images in parallel.  
4. Start PostgreSQL, Redis, the Node API, and the Python sweeper.  
5. Wait for the DB to become healthy and run the Knex migration.

When finished you’ll see:

```
--- Setup Complete! System is running on http://localhost:3000 ---
```

---

## Database Migrations
Schema is defined in `src/db/migrations/20251206_cra_beefed_schema.js`.

```bash
# Run migrations
docker-compose exec node-api npm run migrate          # knex migrate:latest

# Roll back one step
docker-compose exec node-api npm run migrate:rollback
```

The migration creates `artifacts`, `enforcements`, and the `update_updated_at` trigger.

---

## Running the Stack
### Normal mode (worker runs inside the Node container)
```bash
docker-compose up -d
```
The `node-api` container starts the Express server **and** the worker (you can also run the worker manually, see below).

### Optional: Dedicated worker service
Add this service to `docker-compose.yml` (already commented):

```yaml
  worker:
    build:
      context: .
      dockerfile: Dockerfile.node
    command: node dist/worker.js
    depends_on:
      - db
      - redis
    environment:
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - DATABASE_URL=postgres://user:pass@db:5432/cra
```

Start it:

```bash
docker-compose up -d worker
```

---

## API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check (200). |
| `POST` | `/artifacts` | Register a new artifact (hash, lineage, scores). |
| `GET` | `/artifacts/:id` | Retrieve artifact metadata. |
| `POST` | `/enforce` | Create an enforcement job. Body: `{ artifact_id, target, action }`. |
| `GET` | `/enforcements/:id` | View enforcement status and trace data. |

All responses are JSON.

---

## Enforcement Worker
Implemented in `src/enforcement/worker.ts`. It:

1. Listens on the **`enforcements`** BullMQ queue.  
2. Handles `pin_arweave` (uploads artifact JSON to Arweave) and `webhook_alert` (POSTs JSON to a webhook).  
3. Updates the `enforcements` row with `status`, `tx_id`, `inflow_trace`, and any `error_msg`.  
4. Retries failed jobs up to 3 times with exponential back‑off (configurable via `WORKER_CONCURRENCY`).  
5. Gracefully shuts down on `SIGINT`/`SIGTERM`.  

**Run manually (debugging):**

```bash
docker-compose exec node-api node dist/worker.js
```

---

## Python Sweeper / Scorecard
The Python service (`python-sweep`) runs periodically (as defined in `docker-compose.yml`) and:

1. Scans `artifacts` for new entries.  
2. Executes `scorecard.py` to compute `drift_score` and `scorecard_score`.  
3. Inserts a corresponding row into `enforcements` with the desired `action` (e.g., `pin_arweave`).  

Run a single sweep locally:

```bash
cd python
python main.py --sweep-once
```

---

## Environment Variables
| Variable | Default / Example | Purpose |
|----------|-------------------|---------|
| `DATABASE_URL` | `postgres://user:pass@db:5432/cra` | Knex/SQLAlchemy connection string. |
| `REDIS_HOST` | `redis` | Redis host for BullMQ. |
| `REDIS_PORT` | `6379` | Redis port. |
| `ARWEAVE_ENDPOINT` | `https://arweave.net` | Arweave upload endpoint. |
| `WORKER_CONCURRENCY` | `5` | Number of parallel jobs the worker processes. |
| `PYTHONUNBUFFERED` | `1` | Enables real‑time logs from the Python container. |

Override any of these in a `.env` file placed next to `docker-compose.yml`.

---

## Testing the Flow
1. **Create a dummy artifact** (replace `<hash>` with a 64‑char SHA‑256 string):

```bash
curl -X POST http://localhost:3000/artifacts \
  -H "Content-Type: application/json" \
  -d '{"hash":"<hash>","lineage":{},"drift_score":0.12,"scorecard_score":85}'
```

2. **Enqueue an enforcement job**:

```bash
curl -X POST http://localhost:3000/enforce \
  -H "Content-Type: application/json" \
  -d '{"artifact_id":"<artifact‑uuid>","target":"https://example.com/webhook","action":"webhook_alert"}'
```

3. **Observe the worker**:

```bash
docker-compose