# ScalePulse: Production Engineering Reference Architecture

An end-to-end, containerized reference platform demonstrating production reliability patterns across **PostgreSQL, Redis, background workers, progressive canary delivery, and SLO-driven observability**.

scalepulse_prometheus.png

## Architecture Overview
```text
[Client Traffic] 
       │
       ▼
[NGINX Gateway (:8080)] ──(90%)──► [API Stable (v1.0)] ──┐
       │                                                 ├──► [PostgreSQL 16] (Safe DDL / Lock Timeouts)
       └──────────────────(10%)──► [API Canary (v1.1)] ──┘
                                         │
                                         ▼
                                   [Redis 7 Queue] ──► [Background Worker] ──► [Dead Letter Queue]
                                         │
                                         ▼
                                [Prometheus (:9090)] (Golden Signals & SLO Alerts)
```


### 1. Self-Service, Zero-Downtime Database Migrations (`app/db_migrate.py`)
- Enforces `lock_timeout = '2s'` and `statement_timeout = '5s'` so schema changes fail fast rather than stalling live application traffic.
- Uses `CREATE INDEX CONCURRENTLY` outside transaction blocks to prevent table write locks.
- CI pipeline statically blocks destructive DDL (`DROP TABLE`, column type rewrites) before deployment.

### 2. Queue Backpressure & Incident Isolation (`app/main.py` & `app/worker.py`)
- Monitors Redis queue depth on every request and sheds load with `HTTP 429` before worker memory exhaustion occurs.
- Routes failed background jobs to a Dead Letter Queue (`event_dlq`) for zero-data-loss incident recovery.

### 3. Progressive Delivery & Automated Canary Rollback (`deploy/nginx.conf` & `.github/workflows/ci-cd-canary.yml`)
- Splits live traffic 90/10 between stable and canary containers.
- CI/CD pipeline runs automated traffic verification against the gateway and terminates the canary container immediately if an SLO breach (`HTTP 500`) is detected.

### 4. Golden Signals Observability (`deploy/prometheus.yml`)
- Exposes `/metrics` with request rate, error rate, latency histograms (`http_request_duration_seconds`), and queue saturation (`worker_queue_depth`) segmented by deployment version.

## Quickstart & Incident Simulation
1. **Launch Stack:** `docker compose up -d --build`
2. **Verify Canary Split:** `curl -X POST "http://localhost:8080/events?tenant_id=cell-a&payload=hello"`
3. **Simulate Canary Failure & Rollback:** Set `CANARY_FAIL: "true"` in `docker-compose.yml`, run `docker compose up -d api-canary`, and observe 10% error rate spikes in Prometheus (`http://localhost:9090`).

