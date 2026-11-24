import os
import time
import psycopg2
import redis


REDIS_URL=os.getenv("REDIS_URL", "redis://redis:6379/0")
DB_DSN=os.getenv("DB_DSN", "db_name=scalepulse user=postgres password=postgres host=db")
r = redis.from_url(REDIS_URL, decode_responses=True)

def run_worker():
    print("Worker started, polling Redis event queue...")
    while True:
        item = r.brpop("event_queue", timeout=5)
        if not item:
            continue
        _, event_id=item
        try:
            conn=psycopg2.connect(DB_DSN)
            with conn.cursor() as cur:
                time.sleep(0.05)
                cur.execute("UPDATE events SET status= 'PROCESSED' WHERE id=%s", (event_id))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Failed processing {event_id}: {e}")
            r.lpush("event_dlq", event_id)

if __name__="__main__":
    run_worker()

