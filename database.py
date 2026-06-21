import sqlite3
import os

DB_PATH = os.getenv("DB_PATH", "savanna.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            email       TEXT    NOT NULL UNIQUE,
            password    TEXT    NOT NULL,
            city        TEXT    DEFAULT '',
            created_at  TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            date        TEXT    NOT NULL,                 -- YYYY-MM-DD
            travel_kg   REAL    NOT NULL DEFAULT 0,
            food_kg     REAL    NOT NULL DEFAULT 0,
            energy_kg   REAL    NOT NULL DEFAULT 0,
            shop_kg     REAL    NOT NULL DEFAULT 0,
            deed_kg     REAL    NOT NULL DEFAULT 0,       -- negative = offset
            total_kg    REAL    NOT NULL DEFAULT 0,
            travel_name TEXT    DEFAULT '',
            food_name   TEXT    DEFAULT '',
            energy_name TEXT    DEFAULT '',
            shop_name   TEXT    DEFAULT '',
            deed_name   TEXT    DEFAULT '',
            created_at  TEXT    DEFAULT (datetime('now')),
            UNIQUE(user_id, date)
        );

        CREATE TABLE IF NOT EXISTS habits (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title       TEXT    NOT NULL,
            days_done   INTEGER DEFAULT 0,
            accepted_at TEXT    DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_logs_user_date ON logs(user_id, date DESC);
        CREATE INDEX IF NOT EXISTS idx_logs_total     ON logs(total_kg);
    """)

    conn.commit()
    conn.close()
    print("✅ Database initialised at", DB_PATH)
