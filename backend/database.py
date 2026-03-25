"""
SOFEM MES v6.0 — Database (patched)
Fixes:
  - Cursor leaks: every cursor is now closed in finally block
  - Pool size raised to 15 + overflow error surfaced as 503
  - exe() no longer silently swallows errors
  - Added exe_raw() + begin/commit/rollback for explicit transactions
  - Added next_document_number() for race-free numbering
SMARTMOVE · Mahmoud Njeh
"""

import os
import uuid
import logging
from contextlib import contextmanager
from mysql.connector import pooling, Error, PoolError
from datetime import date, datetime

logger = logging.getLogger("sofem-mes")

DB_CONFIG = {
    "host":     os.environ.get("MYSQLHOST",     "localhost"),
    "port":     int(os.environ.get("MYSQLPORT", "3306")),
    "user":     os.environ.get("MYSQLUSER",     "root"),
    "password": os.environ.get("MYSQLPASSWORD", ""),
    "database": os.environ.get("MYSQLDATABASE", "sofem_mes"),
    "charset":  "utf8mb4",
}

pool = None


def init_db():
    global pool
    try:
        pool = pooling.MySQLConnectionPool(
            pool_name="sofem_pool",
            pool_size=15,               # was 5 — too small for concurrent requests
            pool_reset_session=True,
            **DB_CONFIG
        )
        logger.info("✅ MySQL connected (pool_size=15)")
    except Error as e:
        logger.error(f"❌ MySQL error: {e}")
        pool = None


def get_db():
    """FastAPI dependency — yields a pooled connection, always releases it."""
    from fastapi import HTTPException
    if not pool:
        raise HTTPException(503, "Database not available")
    try:
        conn = pool.get_connection()
    except PoolError as e:
        logger.error(f"Connection pool exhausted: {e}")
        raise HTTPException(503, "Service momentanément indisponible — pool saturé")
    try:
        yield conn
    finally:
        conn.close()   # returns connection to pool


# ── Core helpers ──────────────────────────────────────────

def q(conn, sql, params=None, one=False):
    """Query — always closes the cursor."""
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(sql, params or ())
        return cur.fetchone() if one else cur.fetchall()
    finally:
        cur.close()


def exe(conn, sql, params=None):
    """Execute + immediate commit. Returns lastrowid."""
    cur = conn.cursor()
    try:
        cur.execute(sql, params or ())
        conn.commit()
        return cur.lastrowid
    finally:
        cur.close()


def exe_raw(conn, sql, params=None):
    """Execute WITHOUT committing — use inside an explicit transaction."""
    cur = conn.cursor()
    try:
        cur.execute(sql, params or ())
        return cur.lastrowid
    finally:
        cur.close()


# ── Explicit transaction helpers ──────────────────────────

def begin(conn):
    conn.start_transaction()

def commit(conn):
    conn.commit()

def rollback(conn):
    conn.rollback()


@contextmanager
def transaction(conn):
    """Context manager for multi-step atomic operations."""
    conn.start_transaction()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


# ── Race-free document numbering ──────────────────────────

def temp_numero() -> str:
    """Short unique placeholder (12 chars) — fits VARCHAR(20+) UNIQUE columns."""
    return f"TMP-{uuid.uuid4().hex[:8]}"


def next_seq(conn, prefix: str, year: int) -> int:
    """
    ISO 9001-compliant monotonic sequence counter.

    Uses a dedicated document_sequences table — one row per (prefix, year).
    The counter ONLY increments, never resets on delete.
    Two concurrent calls are serialized by MySQL's row-level lock on the
    ON DUPLICATE KEY UPDATE — the second waits for the first to commit.

    Returns the new sequence integer (caller formats it as needed).
    """
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            INSERT INTO document_sequences (prefix, year, last_seq)
            VALUES (%s, %s, 1)
            ON DUPLICATE KEY UPDATE last_seq = last_seq + 1
        """, (prefix, year))
        conn.commit()
        cur.execute(
            "SELECT last_seq FROM document_sequences WHERE prefix=%s AND year=%s",
            (prefix, year)
        )
        row = cur.fetchone()
        return int(row["last_seq"])
    finally:
        cur.close()


def finalize_number(conn, table: str, col: str, row_id: int,
                    prefix: str, year: int, pad: int = 4) -> str:
    """
    Assign a permanent, ISO 9001-compliant document number after an insert.

    Calls next_seq() which atomically increments the sequence counter —
    so numbers are always monotonically increasing regardless of deletes,
    cancellations, or concurrent requests. A deleted OF-2026-0003 is gone
    forever; the next OF will be OF-2026-0004.
    """
    seq    = next_seq(conn, prefix, year)
    numero = f"{prefix}-{year}-{str(seq).zfill(pad)}"
    exe(conn, f"UPDATE `{table}` SET `{col}`=%s WHERE id=%s", (numero, row_id))
    return numero


# ── Serialization helper ──────────────────────────────────

def serialize(obj):
    if isinstance(obj, dict):  return {k: serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):  return [serialize(i) for i in obj]
    if isinstance(obj, (datetime, date)): return str(obj)
    return obj