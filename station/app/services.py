"""Users, quest lifecycle, credit ledger and receipts. All reward decisions happen here."""
import hashlib
import secrets
import threading
import time
import uuid
from pathlib import Path
from datetime import datetime, timezone

from . import receipts
from .config import Settings
from .db import Database

SEED_QUESTS = [
    ("Sunshine Stroll", "Walk a slow lap of the garden without looking at your phone. Notice three things that are green.", 5),
    ("Bench Conversation", "Sit on a bench and ask someone nearby their favourite book or song.", 8),
    ("Cloud Reading", "Lie back or look up for a while. Describe a cloud shape to someone.", 5),
    ("Leaf Collector", "Find three different leaves, compare them, and put them back where you found them.", 6),
]


class ServiceError(Exception):
    def __init__(self, status: int, message: str):
        self.status, self.message = status, message
        super().__init__(message)


def _day(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


class Services:
    def __init__(self, db: Database, settings: Settings, clock=time.time):
        self.db, self.settings, self.now = db, settings, clock
        self._pair_lock = threading.Lock()
        self._pair_codes: dict[str, tuple[str, float]] = {}
        self._claim_fails: list[tuple[float, str]] = []
        if not db.one("SELECT 1 FROM quests LIMIT 1"):
            for t, d, r in SEED_QUESTS:
                db.execute("INSERT INTO quests(title,description,reward) VALUES (?,?,?)", (t, d, r))
        key_path = settings.key_path or (None if settings.db_path == ":memory:" else str(Path(settings.db_path).parent / "receipt_key.pem"))
        self.key = receipts.load_or_create_key(key_path)

    @property
    def public_key(self) -> str:
        return receipts.public_key_b64(self.key)

    # ---- users -----------------------------------------------------------
    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def create_user(self, nickname: str):
        nickname = nickname.strip()
        if not 1 <= len(nickname) <= 24:
            raise ServiceError(422, "nickname must be 1-24 characters")
        uid, token = uuid.uuid4().hex, secrets.token_urlsafe(24)
        self.db.execute("INSERT INTO users VALUES (?,?,?,?)", (uid, nickname, self._hash(token), int(self.now())))
        return {"user_id": uid, "nickname": nickname, "token": token}

    def user_by_token(self, token: str):
        h = self._hash(token or "")
        return (self.db.one("SELECT * FROM users WHERE token_hash=?", (h,)) or
                self.db.one("SELECT u.* FROM users u JOIN device_tokens d ON d.user_id=u.id WHERE d.token_hash=?", (h,)))

    PAIR_TTL = 300
    # Brute-force protection for the 6-digit code: a per-client lockout (so one noisy client cannot lock out
    # everybody else) plus a much higher global ceiling as a backstop against distributed guessing.
    CLAIM_CLIENT_MAX, CLAIM_GLOBAL_MAX, CLAIM_WINDOW = 5, 300, 600

    def create_pair_code(self, user):
        """Short-lived single-use code shown in the web app and typed into the Android app."""
        now = self.now()
        with self._pair_lock:
            self._pair_codes = {c: v for c, v in self._pair_codes.items() if v[1] > now}
            code = f"{secrets.randbelow(10**6):06d}"
            while code in self._pair_codes:
                code = f"{secrets.randbelow(10**6):06d}"
            self._pair_codes[code] = (user["id"], now + self.PAIR_TTL)
        return {"code": code, "expires_in": self.PAIR_TTL}

    def claim_pair_code(self, code: str, label: str, client: str = ""):
        now = self.now()
        with self._pair_lock:
            self._claim_fails = [(t, c) for t, c in self._claim_fails if t > now - self.CLAIM_WINDOW]
            mine = sum(1 for t, c in self._claim_fails if c == client and t > now - 60)
            if mine >= self.CLAIM_CLIENT_MAX or len(self._claim_fails) >= self.CLAIM_GLOBAL_MAX:
                raise ServiceError(429, "too many failed pairing attempts, wait a minute")
            entry = self._pair_codes.pop((code or "").strip(), None)  # pop under lock => strictly single use
            if not entry or entry[1] < now:
                self._claim_fails.append((now, client))
                raise ServiceError(422, "invalid or expired pairing code")
        token = secrets.token_urlsafe(24)
        self.db.execute("INSERT INTO device_tokens VALUES (?,?,?,?)",
                        (self._hash(token), entry[0], label[:40] or "device", int(self.now())))
        user = self.db.one("SELECT * FROM users WHERE id=?", (entry[0],))
        return {"token": token, "user_id": user["id"], "nickname": user["nickname"]}

    # ---- device tokens ----------------------------------------------------
    def list_devices(self, user_id: str):
        return [{"id": r["token_hash"][:12], "label": r["label"], "created_at": r["created_at"]}
                for r in self.db.query("SELECT token_hash,label,created_at FROM device_tokens WHERE user_id=? ORDER BY created_at", (user_id,))]

    def revoke_device(self, user_id: str, device_id: str | None = None, token: str | None = None):
        """Revoke by short id, or the device identified by its own token. Only the owner's devices."""
        if token is not None:
            cur = self.db.execute("DELETE FROM device_tokens WHERE token_hash=? AND user_id=?", (self._hash(token), user_id))
        else:
            cur = self.db.execute("DELETE FROM device_tokens WHERE user_id=? AND substr(token_hash,1,12)=?", (user_id, device_id or ""))
        if cur.rowcount == 0:
            raise ServiceError(404, "device not found")

    def pending_receipts(self, user_id: str):
        rows = self.db.query("SELECT token FROM receipts WHERE user_id=? AND redeemed_at IS NULL AND token IS NOT NULL "
                             "AND issued_at > ? ORDER BY issued_at",
                             (user_id, int(self.now()) - self.settings.receipt_ttl_days * 86400))
        return [r["token"] for r in rows]

    # ---- quests ----------------------------------------------------------
    def list_quests(self):
        return [dict(r) | {"duration_seconds": self.settings.quest_duration}
                for r in self.db.query("SELECT id,title,description,reward,source FROM quests WHERE active=1 ORDER BY id")]

    def add_quest(self, title: str, description: str, source: str):
        # Reward is always chosen by the server, never by the generator or client.
        cur = self.db.execute("INSERT INTO quests(title,description,reward,source) VALUES (?,?,?,?)",
                              (title[:80], description[:400], 5, source))
        return cur.lastrowid

    def start_quest(self, user, quest_id: int, join_code: str | None = None):
        quest = self.db.one("SELECT * FROM quests WHERE id=? AND active=1", (quest_id,))
        if not quest:
            raise ServiceError(404, "quest not found")
        with self.db.transaction():
            if self.db.one("SELECT 1 FROM quest_runs WHERE user_id=? AND quest_id=? AND status='active'", (user["id"], quest_id)):
                raise ServiceError(409, "quest already in progress")
            partner = None
            if join_code:
                partner = self.db.one("SELECT * FROM quest_runs WHERE code=? AND status='active'", (join_code.strip().upper(),))
                if not partner or partner["quest_id"] != quest_id or partner["user_id"] == user["id"]:
                    raise ServiceError(422, "invalid join code")
            run_id = uuid.uuid4().hex
            while True:
                code = secrets.token_hex(3).upper()
                if not self.db.one("SELECT 1 FROM quest_runs WHERE code=?", (code,)):
                    break
            self.db.execute("INSERT INTO quest_runs(id,code,quest_id,user_id,started_at,partner_run_id) VALUES (?,?,?,?,?,?)",
                            (run_id, code, quest_id, user["id"], int(self.now()), partner["id"] if partner else None))
        return {"run_id": run_id, "code": code, "quest_id": quest_id,
                "duration_seconds": self.settings.quest_duration, "shared": partner is not None}

    def complete_run(self, user, run_id: str):
        with self.db.transaction():
            run = self.db.one("SELECT * FROM quest_runs WHERE id=? AND user_id=?", (run_id, user["id"]))
            if not run:
                raise ServiceError(404, "run not found")
            if run["status"] != "active":
                raise ServiceError(409, "run already completed")
            now = self.now()
            remaining = run["started_at"] + self.settings.quest_duration - now
            if remaining > 0:
                raise ServiceError(425, f"quest not finished yet, {int(remaining) + 1}s remaining")
            quest = self.db.one("SELECT * FROM quests WHERE id=?", (run["quest_id"],))
            # Shared activity: this run joined someone else, or someone joined this run.
            partner = None
            if run["partner_run_id"]:
                partner = self.db.one("SELECT * FROM quest_runs WHERE id=?", (run["partner_run_id"],))
            else:
                partner = self.db.one("SELECT * FROM quest_runs WHERE partner_run_id=? ORDER BY started_at LIMIT 1", (run_id,))
            shared = bool(partner) and (partner["started_at"] + self.settings.quest_duration <= now or partner["status"] == "completed")
            self.db.execute("UPDATE quest_runs SET status='completed', completed_at=? WHERE id=?", (int(now), run_id))
            wanted = quest["reward"] + (self.settings.shared_bonus if shared else 0)
            granted = min(wanted, self.daily_remaining(user["id"], now))
            result = {"run_id": run_id, "credits": granted, "shared_bonus": shared and granted > 0, "receipt": None}
            if granted <= 0:
                result["message"] = "daily earning limit reached"
                return result
            cur = self.db.execute(
                "INSERT INTO ledger(user_id,amount,kind,ref,note,day,created_at) VALUES (?,?,?,?,?,?,?)",
                (user["id"], granted, "quest", run_id, quest["title"] + (" (shared)" if shared else ""), _day(now), int(now)))
            rid = uuid.uuid4().hex
            self.db.execute("INSERT INTO receipts(id,ledger_id,user_id,amount,issued_at) VALUES (?,?,?,?,?)",
                            (rid, cur.lastrowid, user["id"], granted, int(now)))
            payload = {"v": 2, "id": rid, "user": user["id"], "amount": granted, "quest": quest["id"], "iat": int(now),
                       "aud": receipts.station_id(self.key), "exp": int(now) + self.settings.receipt_ttl_days * 86400}
            result["receipt"] = receipts.sign(self.key, payload)
            self.db.execute("UPDATE receipts SET token=? WHERE id=?", (result["receipt"], rid))
            return result

    def daily_remaining(self, user_id: str, now: float | None = None) -> int:
        now = self.now() if now is None else now
        row = self.db.one("SELECT COALESCE(SUM(amount),0) s FROM ledger WHERE user_id=? AND day=? AND amount>0",
                          (user_id, _day(now)))
        return max(0, self.settings.daily_limit - row["s"])

    # ---- wallet ----------------------------------------------------------
    def wallet(self, user_id: str):
        bal = self.db.one("SELECT COALESCE(SUM(amount),0) s FROM ledger WHERE user_id=?", (user_id,))["s"]
        hist = [dict(r) for r in self.db.query(
            "SELECT id,amount,kind,note,created_at FROM ledger WHERE user_id=? ORDER BY id DESC LIMIT 100", (user_id,))]
        return {"balance": bal, "daily_remaining": self.daily_remaining(user_id), "history": hist}

    def verify_receipt(self, token: str, redeem: bool = False, caller_id: str | None = None):
        """Check signature, audience (this station) and expiry. Redeeming additionally requires that the caller
        owns the receipt, and is a single atomic UPDATE so concurrent requests cannot both succeed."""
        payload = receipts.verify(self.key, token)
        if not payload:
            raise ServiceError(422, "invalid receipt signature")
        if payload.get("v") != 2 or payload.get("aud") != receipts.station_id(self.key):
            raise ServiceError(422, "receipt was not issued by this station")
        row = self.db.one("SELECT * FROM receipts WHERE id=?", (payload.get("id"),))
        if not row or row["amount"] != payload.get("amount") or row["user_id"] != payload.get("user"):
            raise ServiceError(422, "unknown receipt")
        if redeem:
            if caller_id != row["user_id"]:
                raise ServiceError(403, "receipt belongs to a different participant")
            if payload.get("exp", 0) < self.now():
                raise ServiceError(410, "receipt expired")
            cur = self.db.execute("UPDATE receipts SET redeemed_at=? WHERE id=? AND redeemed_at IS NULL",
                                  (int(self.now()), row["id"]))
            if cur.rowcount == 0:
                raise ServiceError(409, "receipt already redeemed")
            return {"valid": True, "id": row["id"], "amount": row["amount"], "redeemed": True}
        return {"valid": True, "id": row["id"], "amount": row["amount"], "redeemed": row["redeemed_at"] is not None,
                "expired": payload.get("exp", 0) < self.now()}
