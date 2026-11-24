import os
import sys
import psycopg2

DB_DSN=os.getenv("DB_DSN", "dbname=scalepulse user=postgres password=postgres host=db")

SAFE_DDL="""
SET lock_timeout = '2s';

CREATE TABLE IF NOT EXISTS events (
id UUID PRIMARY KEY, 
tenant_id VARCHAR(64) NOT NULL,
payload TEXT NOT NULL,
status VARCHAR(20) NOT NULL,
created_at TIMESTAMP DEFAULT NOW()
);


CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_events_tenant_status ON events (tenant_id, status);
"""

def migrate():
    conn = psycopg2.connect(DB_DSN)
    conn.autocommit=True
    try:
        with conn.cursor() as cur:
            for statement in SAFE_DDL.strip().split(";"):
                if statement.strip():
                    cur.execute(statement)
        print("Migration succeeded safely within 2s lock_timeout.")

    except psycopg2.Error as e:
        print(f"BLOCKED UNSAFE MIGRATION: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__=="__main__":
    migrate()



