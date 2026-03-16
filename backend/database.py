"""
SOFEM MES v2.0 — Database
SMARTMOVE · Mahmoud Njeh
"""

import os
import logging
from mysql.connector import pooling, Error
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
        pool = pooling.MySQLConnectionPool(pool_name="sofem_pool", pool_size=5, **DB_CONFIG)
        logger.info("✅ MySQL connected")
    except Error as e:
        logger.error(f"❌ MySQL error: {e}")
        pool = None

def get_db():
    from fastapi import HTTPException
    if not pool:
        raise HTTPException(503, "Database not available")
    conn = pool.get_connection()
    try:
        yield conn
    finally:
        conn.close()

def q(conn, sql, params=None, one=False):
    cur = conn.cursor(dictionary=True)
    cur.execute(sql, params or ())
    return cur.fetchone() if one else cur.fetchall()

def exe(conn, sql, params=None):
    cur = conn.cursor()
    cur.execute(sql, params or ())
    conn.commit()
    return cur.lastrowid

def serialize(obj):
    if isinstance(obj, dict):  return {k: serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):  return [serialize(i) for i in obj]
    if isinstance(obj, (datetime, date)): return str(obj)
    return obj
