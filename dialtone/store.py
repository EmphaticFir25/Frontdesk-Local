"""SQLite storage: call log, appointments, and messages for every business."""
import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    id INTEGER PRIMARY KEY,
    business TEXT NOT NULL,
    caller_phone TEXT,
    started_at REAL,
    outcome TEXT,
    transcript TEXT
);
CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY,
    business TEXT NOT NULL,
    caller_name TEXT,
    caller_phone TEXT,
    service TEXT,
    starts_at TEXT NOT NULL,   -- ISO 8601 with offset, business local time
    ends_at TEXT NOT NULL,
    status TEXT DEFAULT 'booked',
    created_at REAL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    business TEXT NOT NULL,
    caller_name TEXT,
    caller_phone TEXT,
    message TEXT,
    created_at REAL
);
"""


class Store:
    def __init__(self, path: str | Path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)

    # --- calls -------------------------------------------------------------
    def start_call(self, business: str, caller_phone: str) -> int:
        cur = self.db.execute(
            "INSERT INTO calls (business, caller_phone, started_at) VALUES (?, ?, ?)",
            (business, caller_phone, time.time()),
        )
        self.db.commit()
        return cur.lastrowid

    def end_call(self, call_id: int, outcome: str, transcript: list) -> None:
        self.db.execute(
            "UPDATE calls SET outcome = ?, transcript = ? WHERE id = ?",
            (outcome, json.dumps(transcript), call_id),
        )
        self.db.commit()

    # --- appointments ------------------------------------------------------
    def booked_intervals(self, business: str, day: str) -> list[tuple[datetime, datetime]]:
        """All booked (start, end) pairs for one business on a YYYY-MM-DD date."""
        rows = self.db.execute(
            "SELECT starts_at, ends_at FROM appointments "
            "WHERE business = ? AND status = 'booked' AND starts_at LIKE ?",
            (business, f"{day}%"),
        ).fetchall()
        return [(datetime.fromisoformat(s), datetime.fromisoformat(e)) for s, e in rows]

    def add_appointment(self, business, caller_name, caller_phone, service, starts, ends) -> int:
        cur = self.db.execute(
            "INSERT INTO appointments (business, caller_name, caller_phone, service, "
            "starts_at, ends_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (business, caller_name, caller_phone, service,
             starts.isoformat(), ends.isoformat(), time.time()),
        )
        self.db.commit()
        return cur.lastrowid

    # --- messages ----------------------------------------------------------
    def add_message(self, business, caller_name, caller_phone, message) -> int:
        cur = self.db.execute(
            "INSERT INTO messages (business, caller_name, caller_phone, message, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (business, caller_name, caller_phone, message, time.time()),
        )
        self.db.commit()
        return cur.lastrowid
