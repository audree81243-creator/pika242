import os

import psycopg


def get_connection():
    db_url = (os.getenv("DATABASE_URL") or "").strip()
    if not db_url:
        raise RuntimeError("Missing DATABASE_URL in environment.")
    return psycopg.connect(
        db_url,
        connect_timeout=10,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5,
    )


def fetch_one(query, params=None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchone()


def execute(query, params=None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)


if __name__ == "__main__":
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                result = cur.fetchone()
        print(f"DB connected OK: {result[0]}")
    except Exception as exc:
        print(f"DB connection failed: {exc}")
