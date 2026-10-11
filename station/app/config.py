"""Station configuration, read from environment variables (prefix CG_)."""
import os
from dataclasses import dataclass, field
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent


def _bool(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    db_path: str = field(default_factory=lambda: os.environ.get("CG_DB_PATH", str(BASE / "data" / "station.db")))
    media_dir: str = field(default_factory=lambda: os.environ.get("CG_MEDIA_DIR", str(BASE / "media")))
    station_name: str = field(default_factory=lambda: os.environ.get("CG_STATION_NAME", "Garden Bench #1"))
    # ECDSA P-256 private key (PEM) for signing receipts; default: receipt_key.pem next to the DB.
    key_path: str = field(default_factory=lambda: os.environ.get("CG_KEY_PATH", ""))
    receipt_ttl_days: int = field(default_factory=lambda: int(os.environ.get("CG_RECEIPT_TTL_DAYS", "30")))
    demo_mode: bool = field(default_factory=lambda: _bool("CG_DEMO_MODE", True))
    demo_quest_seconds: int = field(default_factory=lambda: int(os.environ.get("CG_DEMO_QUEST_SECONDS", "10")))
    quest_seconds: int = field(default_factory=lambda: int(os.environ.get("CG_QUEST_SECONDS", "600")))
    daily_limit: int = field(default_factory=lambda: int(os.environ.get("CG_DAILY_LIMIT", "30")))
    shared_bonus: int = field(default_factory=lambda: int(os.environ.get("CG_SHARED_BONUS", "2")))
    # AI: local Ollama-compatible runtime serving a Gemma model; falls back to canned content.
    ai_url: str = field(default_factory=lambda: os.environ.get("CG_AI_URL", "http://127.0.0.1:11434"))
    ai_model: str = field(default_factory=lambda: os.environ.get("CG_AI_MODEL", "gemma3:1b"))
    ai_enabled: bool = field(default_factory=lambda: _bool("CG_AI_ENABLED", True))
    ai_timeout: float = field(default_factory=lambda: float(os.environ.get("CG_AI_TIMEOUT", "20")))
    elevenlabs_key: str = field(default_factory=lambda: os.environ.get("ELEVENLABS_API_KEY", ""))
    elevenlabs_voice: str = field(default_factory=lambda: os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM"))
    # Optional command run with the event name as argument to drive LEDs / LED matrix.
    led_command: str = field(default_factory=lambda: os.environ.get("CG_LED_COMMAND", ""))
    trivia_seconds: int = field(default_factory=lambda: int(os.environ.get("CG_TRIVIA_SECONDS", "15")))

    @property
    def quest_duration(self) -> int:
        return self.demo_quest_seconds if self.demo_mode else self.quest_seconds
