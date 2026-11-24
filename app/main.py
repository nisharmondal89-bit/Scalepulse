import os
import time
import uuid
import psycopg2
import redis
from fastapi import FastAPI, HTTPException, Response
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

app=FastAPI(title="ScalePulse")
VERSION=os.getenv("APP_VERSION", "v1-stable")
REDIS_URL=os.getenv("REDIS_URL", "redis://redis:6379/0")
DB_DSN=os.getenv("DB_DSN", "dbname=scalepulse user=postgres password=postgres host=db")

r=redis.from_url(REDIS_URL, decode_responses=True)

REQUEST_COUNT=Counter("http_requests_total", "Total HTTP Requests", ["method", "endpoint", "status", "version"])
REQUEST_LATENCY=Histogram("http_request_duration_seconds", "HTTP Latency", ["endpoint", "version"], buckets=[0.05, 0.1, 0.25, 0.5, 1.0])
QUEUE_DEPTH=Gauge("worker_queue_depth", "Current jobs waiting in Redis")

def get_db():
    return psycopg2.connect(DB_DSN)


@app.get("/healthz")
def health():
    return {"status": "ok", "version": VERSION}

@app.post("/events")
def ingest_event(tenant_id: str, payload: str):
    start = time.time()

    depth= r.llen("event_queue")
    QUEUE_DEPTH.set(depth)
    if depth > 500: 
        REQUEST_COUNT.labels("POST", "/events", "429", VERSION).inc()
        raise HTTPException(status_code=429, detail="Queue backpressure limit reached")

    if os.getenv("CANARY_FAIL") == "true":
        REQUEST_COUNT.labels("POST", "/events", "500", VERSION).inc()
        raise HTTPException(status_code=500, detail="Simulate canary regression")

    event_id=str(uuid.uuid4())
    conn=get_db()
    with conn.cursor() as cur:
        cur.execute(
                "INSERT INTO events (id, tenant_id, payload, status) VALUES (%s, %s, %s, 'QUEUED')",
                (event_id, tenant_id, payload)
                )
    conn.commit()
    conn.close()

    r.lpush("event_queue", event_id)
    QUEUE_DEPTH.set(r.llen("event_queue"))

    REQUEST_LATENCY.labels("/events", VERSION).observe(time.time() - start)
    REQUEST_COUNT.labels("POST", "/events", "200", VERSION).inc()
    return {"event_id": event_id, "served_by": VERSION}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)






