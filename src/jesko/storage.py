from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from .schema import Event, stable_id


class Storage:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=10, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(
            """CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY,
                dedupe_key TEXT UNIQUE,
                payload TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0,
                next_attempt REAL NOT NULL DEFAULT 0,
                created_at REAL NOT NULL,
                claimed_at REAL,
                claim_token TEXT
            );
            CREATE TABLE IF NOT EXISTS cooldowns (
                key TEXT PRIMARY KEY,
                until REAL NOT NULL
            );"""
        )
        self._migrate()
        self.db.commit()

    def _migrate(self):
        cols = {r[1] for r in self.db.execute("PRAGMA table_info(events)")}
        for name, typ in (("claimed_at", "REAL"), ("claim_token", "TEXT")):
            if name not in cols:
                self.db.execute(f"ALTER TABLE events ADD COLUMN {name} {typ}")

    def add(self, event: Event) -> bool:
        key = f"{event.source}:{event.session_id or ''}:{event.turn_id or event.event_id}:{event.event_type}"
        try:
            self.db.execute(
                "INSERT INTO events(dedupe_key,payload,created_at) VALUES(?,?,?)", (key, event.to_json(), time.time())
            )
            self.db.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def pending(self, limit=50):
        return self.db.execute(
            "SELECT * FROM events WHERE status IN ('pending','failed') AND next_attempt<=? ORDER BY id LIMIT ?",
            (time.time(), limit),
        ).fetchall()

    def claim(self, limit=50, lease_seconds=120):
        now, token = time.time(), stable_id([time.time(), id(self)])
        with self.db:
            self.db.execute(
                "UPDATE events SET status='pending', claim_token=NULL, "
                "claimed_at=NULL WHERE status='processing' AND claimed_at<?",
                (now - lease_seconds,),
            )
            ids = [
                r[0]
                for r in self.db.execute(
                    "SELECT id FROM events WHERE status IN ('pending','failed') "
                    "AND next_attempt<=? ORDER BY id LIMIT ?",
                    (now, limit),
                )
            ]
            if ids:
                marks = ",".join("?" for _ in ids)
                self.db.execute(
                    f"UPDATE events SET status='processing', claim_token=?, claimed_at=? WHERE id IN ({marks})",
                    (token, now, *ids),
                )
            return self.db.execute("SELECT * FROM events WHERE claim_token=? ORDER BY id", (token,)).fetchall()

    def release_claim(self, row_id: int, claim_token: str, status: str = "pending"):
        self.db.execute(
            "UPDATE events SET status=?, claim_token=NULL, claimed_at=NULL WHERE id=? AND claim_token=?",
            (status, row_id, claim_token),
        )
        self.db.commit()

    def mark(self, row_id: int, status: str, attempts: int = 0, delay: float = 0, claim_token: str | None = None):
        self.db.execute(
            "UPDATE events SET status=?, attempts=?, next_attempt=?, "
            "claim_token=NULL, claimed_at=NULL WHERE id=? AND "
            "(claim_token=? OR claim_token IS NULL)",
            (status, attempts, time.time() + delay, row_id, claim_token),
        )
        self.db.commit()

    def cooldown_ready(self, key: str) -> bool:
        row = self.db.execute("SELECT until FROM cooldowns WHERE key=?", (key,)).fetchone()
        return not row or row[0] <= time.time()

    def set_cooldown(self, key: str, seconds: float):
        self.db.execute(
            "INSERT INTO cooldowns(key,until) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET until=excluded.until",
            (key, time.time() + seconds),
        )
        self.db.commit()

    def close(self):
        self.db.close()

    def cleanup(self, retention_days: int = 7):
        self.db.execute(
            "DELETE FROM events WHERE status='sent' AND created_at < ?", (time.time() - retention_days * 86400,)
        )
        self.db.commit()
