import asyncio
import json
import logging
import urllib.request
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import ai
from .config import Settings
from .db import Database
from .games import TriviaManager
from .hardware import make_display
from .library import Library
from .services import ServiceError, Services

STATIC = Path(__file__).parent / "static"
REPORT_HIDE_THRESHOLD = 3


class NickIn(BaseModel):
    nickname: str


class StartIn(BaseModel):
    join_code: str | None = None


class ReceiptIn(BaseModel):
    receipt: str


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=500)


class ReportIn(BaseModel):
    message_id: int
    reason: str = Field(default="inappropriate", max_length=200)


class BlockIn(BaseModel):
    user_id: str


def create_app(settings: Settings | None = None, provider=None, clock=None) -> FastAPI:
    settings = settings or Settings()
    db = Database(settings.db_path)
    svc = Services(db, settings, **({"clock": clock} if clock else {}))
    display = make_display(settings.led_command)
    library = Library(settings.media_dir)
    trivia = TriviaManager(settings.trivia_seconds, display.show)
    if provider is None and settings.ai_enabled:
        provider = ai.OllamaProvider(settings)
    display.show("boot")

    app = FastAPI(title="CommonGround Station")
    app.state.svc, app.state.display, app.state.trivia = svc, display, trivia

    @app.exception_handler(ServiceError)
    async def _svc_err(_, exc: ServiceError):
        return JSONResponse({"detail": exc.message}, status_code=exc.status)

    def current_user(authorization: str = Header(default="")):
        user = svc.user_by_token(authorization.removeprefix("Bearer ").strip())
        if not user:
            raise HTTPException(401, "missing or invalid session token")
        return user

    # ---- station ---------------------------------------------------------
    @app.get("/api/status")
    def status():
        return {"station": settings.station_name, "demo_mode": settings.demo_mode,
                "quest_seconds": settings.quest_duration, "daily_limit": settings.daily_limit,
                "ai": "local-model-with-fallback" if settings.ai_enabled else "fallback-only", "ai_model": settings.ai_model,
                "online_required": False, "rooms": {n: {"players": len(r.players), "state": r.state}
                                                    for n, r in trivia.rooms.items()}}

    @app.post("/api/session")
    def session(body: NickIn):
        return svc.create_user(body.nickname)

    @app.get("/api/pair")
    def pair(user=Depends(current_user)):
        """Gives the Android companion what it needs to verify receipts offline."""
        return {"station": settings.station_name, "receipt_key": svc.secret, "user_id": user["id"]}

    # ---- quests / wallet -------------------------------------------------
    @app.get("/api/quests")
    def quests():
        return svc.list_quests()

    @app.post("/api/quests/{quest_id}/start")
    def start_quest(quest_id: int, body: StartIn | None = None, user=Depends(current_user)):
        out = svc.start_quest(user, quest_id, body.join_code if body else None)
        display.show("quest_started")
        return out

    @app.post("/api/runs/{run_id}/complete")
    def complete(run_id: str, user=Depends(current_user)):
        out = svc.complete_run(user, run_id)
        if out["credits"] > 0:
            display.show("quest_completed")
        return out

    @app.get("/api/wallet")
    def wallet(user=Depends(current_user)):
        return svc.wallet(user["id"])

    @app.post("/api/receipts/verify")
    def verify(body: ReceiptIn):
        return svc.verify_receipt(body.receipt)

    @app.post("/api/receipts/redeem")
    def redeem(body: ReceiptIn):
        return svc.verify_receipt(body.receipt, redeem=True)

    # ---- AI --------------------------------------------------------------
    @app.post("/api/ai/quest")
    async def ai_quest(user=Depends(current_user)):
        out = await asyncio.to_thread(ai.generate, "quest", provider)
        qid = svc.add_quest(out["title"], out["description"], out["source"])
        display.show("new_activity")
        return out | {"quest_id": qid}

    @app.post("/api/ai/discussion")
    async def ai_discussion(user=Depends(current_user)):
        out = await asyncio.to_thread(ai.generate, "discussion", provider)
        db.execute("INSERT INTO messages(user_id,nickname,body,created_at) VALUES ('station','Station',?,?)",
                   (out["question"], int(svc.now())))
        return out

    @app.post("/api/radio")
    async def radio(user=Depends(current_user)):
        out = await asyncio.to_thread(ai.generate, "radio", provider)
        out["audio"] = None
        if settings.elevenlabs_key:
            out["audio"] = await asyncio.to_thread(_narrate, out["script"])
        return out

    def _narrate(text: str):
        """Optional ElevenLabs narration (needs internet); result is cached for offline playback."""
        import hashlib
        name = "radio-" + hashlib.sha1(text.encode()).hexdigest()[:10] + ".mp3"
        path = library.cache_path(name)
        if path.exists():
            return name
        try:
            req = urllib.request.Request(
                f"https://api.elevenlabs.io/v1/text-to-speech/{settings.elevenlabs_voice}",
                json.dumps({"text": text, "model_id": "eleven_multilingual_v2"}).encode(),
                {"xi-api-key": settings.elevenlabs_key, "Content-Type": "application/json", "Accept": "audio/mpeg"})
            with urllib.request.urlopen(req, timeout=30) as r:
                path.write_bytes(r.read())
            return name
        except Exception as exc:
            logging.getLogger("commonground").warning("ElevenLabs narration failed: %s", exc)
            return None

    # ---- talk circle -----------------------------------------------------
    @app.get("/api/talk")
    def talk(user=Depends(current_user)):
        rows = db.query(
            "SELECT id,user_id,nickname,body,created_at FROM messages WHERE hidden=0 AND user_id NOT IN "
            "(SELECT blocked_id FROM blocks WHERE blocker_id=?) ORDER BY id DESC LIMIT 100", (user["id"],))
        return [dict(r) for r in reversed(rows)]

    @app.post("/api/talk")
    def talk_post(body: MessageIn, user=Depends(current_user)):
        cur = db.execute("INSERT INTO messages(user_id,nickname,body,created_at) VALUES (?,?,?,?)",
                         (user["id"], user["nickname"], body.body.strip(), int(svc.now())))
        return {"id": cur.lastrowid}

    @app.post("/api/report")
    def report(body: ReportIn, user=Depends(current_user)):
        if not db.one("SELECT 1 FROM messages WHERE id=?", (body.message_id,)):
            raise HTTPException(404, "message not found")
        db.execute("INSERT OR IGNORE INTO reports(reporter_id,message_id,reason,created_at) VALUES (?,?,?,?)",
                   (user["id"], body.message_id, body.reason, int(svc.now())))
        n = db.one("SELECT COUNT(*) c FROM reports WHERE message_id=?", (body.message_id,))["c"]
        if n >= REPORT_HIDE_THRESHOLD:
            db.execute("UPDATE messages SET hidden=1 WHERE id=?", (body.message_id,))
        return {"reports": n}

    @app.post("/api/block")
    def block(body: BlockIn, user=Depends(current_user)):
        if body.user_id == user["id"]:
            raise HTTPException(422, "cannot block yourself")
        db.execute("INSERT OR IGNORE INTO blocks VALUES (?,?)", (user["id"], body.user_id))
        return {"blocked": body.user_id}

    # ---- library ---------------------------------------------------------
    @app.get("/api/library/{section}")
    def lib_list(section: str):
        if section not in ("music", "books", "cache"):
            raise HTTPException(404)
        return library.list(section)

    @app.get("/api/library/{section}/{name}")
    def lib_file(section: str, name: str):
        p = library.path(section, name)
        if not p:
            raise HTTPException(404, "file not found")
        return FileResponse(p)

    # ---- trivia ----------------------------------------------------------
    @app.websocket("/ws/trivia/{room_name}")
    async def trivia_ws(ws: WebSocket, room_name: str, token: str = ""):
        user = svc.user_by_token(token)
        if not user or len(room_name) > 32:
            await ws.close(code=4401)
            return
        await ws.accept()
        room = trivia.room(room_name)
        await trivia.join(room, user, ws)
        try:
            while True:
                msg = await ws.receive_json()
                if isinstance(msg, dict):
                    await trivia.handle(room, user, msg)
        except (WebSocketDisconnect, json.JSONDecodeError, RuntimeError):
            pass
        finally:
            await trivia.leave(room, user["id"])

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app


def app_factory() -> FastAPI:
    return create_app()
