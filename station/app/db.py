import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY, nickname TEXT NOT NULL, token_hash TEXT NOT NULL UNIQUE, created_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS quests (
  id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, description TEXT NOT NULL,
  reward INTEGER NOT NULL, source TEXT NOT NULL DEFAULT 'builtin', active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS quest_runs (
  id TEXT PRIMARY KEY, code TEXT NOT NULL UNIQUE, quest_id INTEGER NOT NULL REFERENCES quests(id),
  user_id TEXT NOT NULL REFERENCES users(id), started_at INTEGER NOT NULL,
  partner_run_id TEXT, status TEXT NOT NULL DEFAULT 'active', completed_at INTEGER);
CREATE TABLE IF NOT EXISTS ledger (
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL REFERENCES users(id),
  amount INTEGER NOT NULL, kind TEXT NOT NULL, ref TEXT NOT NULL, note TEXT NOT NULL DEFAULT '',
  day TEXT NOT NULL, created_at INTEGER NOT NULL, UNIQUE(kind, ref));
CREATE TABLE IF NOT EXISTS receipts (
  id TEXT PRIMARY KEY, ledger_id INTEGER NOT NULL REFERENCES ledger(id), user_id TEXT NOT NULL,
  amount INTEGER NOT NULL, issued_at INTEGER NOT NULL, redeemed_at INTEGER);
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, nickname TEXT NOT NULL,
  body TEXT NOT NULL, hidden INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS blocks (
  blocker_id TEXT NOT NULL, blocked_id TEXT NOT NULL, PRIMARY KEY (blocker_id, blocked_id));
CREATE TABLE IF NOT EXISTS reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT, reporter_id TEXT NOT NULL, message_id INTEGER NOT NULL,
  reason TEXT NOT NULL, created_at INTEGER NOT NULL, UNIQUE(reporter_id, message_id));
"""


class Database:
    def __init__(self, path: str):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        with self.lock:
            self.conn.executescript(SCHEMA)

    def query(self, sql, params=()):
        with self.lock:
            return self.conn.execute(sql, params).fetchall()

    def one(self, sql, params=()):
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def execute(self, sql, params=()):
        with self.lock:
            return self.conn.execute(sql, params)

    @contextmanager
    def transaction(self):
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                yield self
            except BaseException:
                self.conn.execute("ROLLBACK")
                raise
            else:
                self.conn.execute("COMMIT")
