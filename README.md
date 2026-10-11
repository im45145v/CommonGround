# CommonGround — Outside First. Scroll Later.

A local-first campus social commons designed to run on an **Arduino UNO Q** station. Students connect a phone to the
station, complete short outdoor quests, and earn "Social Battery" credits via signed receipts, which an Android
companion is meant to spend as a voluntary recreational screen-time budget.

> **Status: honest prototype.** The station (backend + mobile web app) is implemented and tested on a development
> machine. The Android companion, on-device UNO Q deployment/testing, Gemma on real hardware and ElevenLabs
> integration have **not** been built/verified yet — see [Known limitations](#known-limitations).

## What works today (station/)

| Area | Implementation |
|---|---|
| Station + mobile web app | FastAPI serves a responsive single-page UI (`station/app/static/index.html`); no internet needed |
| Quests & credits | Server-timed quest runs (demo 10 s, normal `CG_QUEST_SECONDS`), server-decided rewards, daily limit, shared-activity bonus via join code, idempotent ledger (`UNIQUE(kind, ref)`) |
| Receipts | HMAC-SHA256 signed, unique, single-redeem receipts (`/api/receipts/verify`, `/redeem`); phone can verify offline with the key from `/api/pair` |
| Library | Music, public-domain books (Aesop selection), cached audio under `station/media/` (separate from code; point `CG_MEDIA_DIR` at an SSD) |
| Multiplayer | WebSocket trivia (`/ws/trivia/{room}`), multiple rooms/players |
| Community | Pseudonymous sessions, Talk Circle, report (auto-hide at 3 reports) and block |
| AI | Replaceable provider interface (`app/ai.py`); local Ollama-compatible runtime serving Gemma (`CG_AI_MODEL`, default `gemma3:1b`); timeouts/malformed output → fallback. Responses state `source: gemma` or `fallback` |
| Radio | `/api/radio` script; optional ElevenLabs narration cached in `media/cache` when `ELEVENLABS_API_KEY` is set (untested against the live API) |
| Hardware feedback | `app/hardware.py` abstraction; no-op by default, or `CG_LED_COMMAND` runs a script with the event name (`boot`, `quest_started`, `quest_completed`, `new_activity`, `game_running`, `game_finished`) |

## Architecture

```
Phone browser ──HTTP/WS──► FastAPI (station/app/main.py)
                             ├─ services.py  users, quests, ledger, receipts (SQLite via db.py)
                             ├─ games.py     trivia rooms (WebSockets)
                             ├─ library.py   media folders
                             ├─ ai.py        provider interface + fallback
                             └─ hardware.py  LED display interface
Android companion ──► /api/pair, receipts (verify offline with HMAC key)   [not implemented]
```

## Run on a development machine

```bash
cd station
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q tests
uvicorn app.main:app_factory --factory --host 0.0.0.0 --port 8000
```
Open `http://<your-ip>:8000` on a phone on the same network.

Settings (env vars): `CG_DEMO_MODE`, `CG_DEMO_QUEST_SECONDS`, `CG_QUEST_SECONDS`, `CG_DAILY_LIMIT`, `CG_SHARED_BONUS`,
`CG_SECRET` (receipt key; otherwise generated and stored in the DB), `CG_DB_PATH`, `CG_MEDIA_DIR`, `CG_AI_URL`,
`CG_AI_MODEL`, `CG_AI_ENABLED`, `CG_AI_TIMEOUT`, `CG_LED_COMMAND`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`.

## Deploy to the UNO Q (untested)

The UNO Q's Linux side (Debian) should be able to run the same commands. Copy `station/`, install requirements,
run uvicorn (e.g. as a systemd service), and join the phones through a local router/hotspot — whether the board can
host its own access point has **not** been verified. Optionally install Ollama/llama.cpp and `ollama pull gemma3:1b`;
check RAM and latency first, and leave `CG_AI_ENABLED=false` if it is not reliable.

## Known limitations

- **Android companion not implemented** (wallet, receipt sync, usage access, voluntary app gate). Receipt format
  and `/api/pair` are designed for it; no Kotlin code exists yet.
- Receipts use a **symmetric** HMAC key shared with paired phones; a compromised phone could mint receipts. Asymmetric
  signatures (e.g. Ed25519) would be the next step. Server-side `/redeem` prevents double redemption online; offline
  dedupe is the client's job (by receipt id).
- The quest timer proves elapsed time only; there is no proof of being outdoors (deliberately no location tracking).
- Session tokens are bearer tokens stored in the browser; no rate limiting.
- Not tested on UNO Q hardware; Gemma local inference, LED matrix output and ElevenLabs were not exercised.
- Talk Circle is polling-based, not real-time.
- Credit farming with multiple anonymous sessions (including self-joined shared quests) is not prevented; the daily
  limit is per pseudonym. Rate limiting or per-device limits are future work. `/api/receipts/redeem` is unauthenticated
  (the signed receipt itself is the bearer credential).
