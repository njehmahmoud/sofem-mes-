"""
SOFEM MES v6.0 — Database (Commit 01 — ISO 9001 soft delete + audit trail)
Changes:
  - Added log_activity() helper — logs every action to activity_log_v2
  - Added soft_delete() helper — never physically deletes, always logs
  - Added cancel_document() helper — cancels a document with reason
  - _ensure_sequences_table now also ensures activity_log_v2 exists
SMARTMOVE · Mahmoud Njeh
"""

import os
import uuid
import json
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
            pool_size=5,
            pool_reset_session=True,
            **DB_CONFIG
        )
        logger.info("✅ MySQL connected (pool_size=15)")
        _ensure_sequences_table()
        _ensure_activity_log()
        _ensure_br_price_column()
    except Error as e:
        logger.error(f"❌ MySQL error: {e}")
        pool = None


def _ensure_sequences_table():
    """
    Create document_sequences if it doesn't exist, then seed it from
    existing document numbers so the counter is always ahead of what's
    already in the database. Safe to call on every startup — fully idempotent.
    """
    try:
        conn = pool.get_connection()
    except Exception as e:
        logger.error(f"_ensure_sequences_table: could not get connection: {e}")
        return
    try:
        cur = conn.cursor()

        # 1. Create the table if missing
        cur.execute("""
            CREATE TABLE IF NOT EXISTS document_sequences (
                prefix   VARCHAR(20)  NOT NULL,
                year     SMALLINT     NOT NULL,
                last_seq INT UNSIGNED NOT NULL DEFAULT 0,
                updated_at TIMESTAMP  DEFAULT CURRENT_TIMESTAMP
                            ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (prefix, year)
            ) ENGINE=InnoDB
        """)
        conn.commit()

        # 2. Seed each prefix from existing data so counter never goes backwards
        seeds = [
            ("OF", "ordres_fabrication", "numero"),
            ("DA", "demandes_achat",     "da_numero"),
            ("BC", "bons_commande",      "bc_numero"),
            ("BR", "bons_reception",     "br_numero"),
            ("BL", "bons_livraison",     "bl_numero"),
        ]
        for prefix, table, col in seeds:
            try:
                cur.execute(f"""
                    INSERT INTO document_sequences (prefix, year, last_seq)
                    SELECT %s, YEAR(created_at),
                           MAX(CAST(SUBSTRING_INDEX(`{col}`, '-', -1) AS UNSIGNED))
                    FROM `{table}`
                    WHERE `{col}` REGEXP %s
                    GROUP BY YEAR(created_at)
                    ON DUPLICATE KEY UPDATE
                        last_seq = GREATEST(last_seq, VALUES(last_seq))
                """, (prefix, f'^{prefix}-[0-9]{{4}}-[0-9]+$'))
                conn.commit()
            except Exception as e:
                logger.warning(f"Seed skipped for {prefix} ({table}): {e}")

        logger.info("✅ document_sequences ready")
    except Exception as e:
        logger.error(f"_ensure_sequences_table failed: {e}")
    finally:
        try: cur.close()
        except: pass
        conn.close()


def _ensure_activity_log():
    """
    Create activity_log_v2 if it doesn't exist.
    This is the ISO 9001 compliant audit trail table.
    Safe to call on every startup — fully idempotent.
    """
    try:
        conn = pool.get_connection()
    except Exception as e:
        logger.error(f"_ensure_activity_log: could not get connection: {e}")
        return
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS activity_log_v2 (
                id              BIGINT        NOT NULL AUTO_INCREMENT,
                created_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
                user_id         INT           NULL,
                user_nom        VARCHAR(100)  NULL,
                action          VARCHAR(50)   NOT NULL,
                entity_type     VARCHAR(50)   NOT NULL,
                entity_id       INT           NULL,
                entity_numero   VARCHAR(50)   NULL,
                old_value       JSON          NULL,
                new_value       JSON          NULL,
                reason          VARCHAR(500)  NULL,
                ip_address      VARCHAR(45)   NULL,
                session_token   VARCHAR(20)   NULL,
                detail          TEXT          NULL,
                PRIMARY KEY (id),
                INDEX idx_entity  (entity_type, entity_id),
                INDEX idx_user    (user_id),
                INDEX idx_action  (action),
                INDEX idx_created (created_at),
                INDEX idx_numero  (entity_numero)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        conn.commit()
        logger.info("✅ activity_log_v2 ready")
    except Exception as e:
        logger.error(f"_ensure_activity_log failed: {e}")
    finally:
        try: cur.close()
        except: pass
        conn.close()


def _ensure_br_price_column():
    """
    Ensure br_lignes table has prix_unitaire column.
    This column stores the unit price at the time of reception.
    Safe to call on every startup — fully idempotent.
    """
    try:
        conn = pool.get_connection()
    except Exception as e:
        logger.error(f"_ensure_br_price_column: could not get connection: {e}")
        return
    try:
        cur = conn.cursor()
        # Check if column exists
        cur.execute("""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME='br_lignes' AND COLUMN_NAME='prix_unitaire'
        """)
        result = cur.fetchone()
        if result and result[0] == 0:
            # Column doesn't exist, add it
            cur.execute("""
                ALTER TABLE br_lignes ADD COLUMN prix_unitaire FLOAT DEFAULT 0
            """)
            conn.commit()
            logger.info("✅ br_lignes.prix_unitaire column added")
        else:
            logger.debug("✅ br_lignes.prix_unitaire column already exists")
    except Exception as e:
        logger.warning(f"_ensure_br_price_column: {e}")
    finally:
        try: cur.close()
        except: pass
        conn.close()


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
    """Start an explicit transaction — silently closes any pending implicit one first."""
    try:
        conn.commit()          # flush any implicit transaction left open by q() calls
    except Exception:
        pass
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
    so numbers are always monotonically increasing regardless of cancellations
    or concurrent requests. A cancelled OF-2026-0003 is gone forever;
    the next OF will be OF-2026-0004.
    """
    seq    = next_seq(conn, prefix, year)
    numero = f"{prefix}-{year}-{str(seq).zfill(pad)}"
    exe(conn, f"UPDATE `{table}` SET `{col}`=%s WHERE id=%s", (numero, row_id))
    return numero


# ── ISO 9001 Audit Trail ──────────────────────────────────

def log_activity(
    conn,
    action:        str,
    entity_type:   str,
    entity_id:     int   = None,
    entity_numero: str   = None,
    user_id:       int   = None,
    user_nom:      str   = None,
    old_value:     dict  = None,
    new_value:     dict  = None,
    reason:        str   = None,
    detail:        str   = None,
    ip_address:    str   = None,
    session_token: str   = None,
):
    """
    ISO 9001 compliant audit trail entry.

    Call this for every significant action:
    - CREATE, UPDATE, CANCEL, APPROVE, REJECT, PRINT, LOGIN, LOGOUT

    Never raises — logging failure must not break the main operation.
    old_value and new_value are stored as JSON for full diff history.
    """
    try:
        old_json = json.dumps(serialize(old_value), ensure_ascii=False) if old_value else None
        new_json = json.dumps(serialize(new_value), ensure_ascii=False) if new_value else None

        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO activity_log_v2
                    (action, entity_type, entity_id, entity_numero,
                     user_id, user_nom, old_value, new_value,
                     reason, detail, ip_address, session_token)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                action, entity_type, entity_id, entity_numero,
                user_id, user_nom, old_json, new_json,
                reason, detail, ip_address, session_token
            ))
            conn.commit()
        finally:
            cur.close()
    except Exception as e:
        logger.warning(f"log_activity failed (non-fatal): {e}")


def soft_delete(
    conn,
    table:         str,
    record_id:     int,
    user_id:       int   = None,
    user_nom:      str   = None,
    reason:        str   = None,
    entity_type:   str   = None,
    entity_numero: str   = None,
):
    """
    ISO 9001 soft delete — sets actif=FALSE, never physically deletes.

    Use for: materiaux, machines, operateurs, clients, fournisseurs, users.
    Logs the deactivation to activity_log_v2 automatically.
    """
    now = datetime.now()

    # Check if table has deactivated_by column
    try:
        exe(conn, f"""
            UPDATE `{table}`
            SET actif = FALSE,
                deactivated_by = %s,
                deactivated_at = %s,
                deactivation_reason = %s
            WHERE id = %s
        """, (user_id, now, reason, record_id))
    except Exception:
        # Fallback: table only has actif column
        exe(conn, f"UPDATE `{table}` SET actif = FALSE WHERE id = %s", (record_id,))

    # Log the action
    log_activity(
        conn,
        action        = "DEACTIVATE",
        entity_type   = entity_type or table.upper(),
        entity_id     = record_id,
        entity_numero = entity_numero,
        user_id       = user_id,
        user_nom      = user_nom,
        reason        = reason,
        detail        = f"Record {record_id} in {table} deactivated"
    )


def cancel_document(
    conn,
    table:         str,
    id_col:        str,
    numero_col:    str,
    record_id:     int,
    user_id:       int,
    user_nom:      str,
    reason:        str,
    entity_type:   str,
    old_statut:    str   = None,
):
    """
    ISO 9001 document cancellation.

    Use for: ordres_fabrication, bons_livraison, demandes_achat,
             bons_commande, ordres_maintenance.

    - Sets statut = 'CANCELLED'
    - Records who cancelled, when, and why
    - Logs full audit trail
    - Reason is MANDATORY — raises ValueError if empty
    """
    if not reason or not reason.strip():
        raise ValueError("Une raison est obligatoire pour annuler un document (ISO 9001)")

    now = datetime.now()

    # Get current state for audit trail
    row = q(conn, f"SELECT * FROM `{table}` WHERE `{id_col}` = %s", (record_id,), one=True)
    if not row:
        from fastapi import HTTPException
        raise HTTPException(404, "Document introuvable")

    numero = row.get(numero_col, str(record_id))

    # Update document
    exe(conn, f"""
        UPDATE `{table}`
        SET statut       = 'CANCELLED',
            cancel_reason = %s,
            cancelled_by  = %s,
            cancelled_at  = %s
        WHERE `{id_col}` = %s
    """, (reason.strip(), user_id, now, record_id))

    # Full audit log
    log_activity(
        conn,
        action        = "CANCEL",
        entity_type   = entity_type,
        entity_id     = record_id,
        entity_numero = numero,
        user_id       = user_id,
        user_nom      = user_nom,
        old_value     = {"statut": old_statut or row.get("statut")},
        new_value     = {"statut": "CANCELLED"},
        reason        = reason.strip(),
        detail        = f"{entity_type} {numero} annulé par {user_nom}"
    )

    return numero


# ── Serialization helper ──────────────────────────────────

def serialize(obj):
    if isinstance(obj, dict):  return {k: serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):  return [serialize(i) for i in obj]
    if isinstance(obj, (datetime, date)): return str(obj)
    return obj