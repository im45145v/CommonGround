# Android companion: build, install, validate on a first phone

## Verification status (read first)
| Item | Status |
|---|---|
| Station tests (`pytest`, 35) | **Run and passing** in the dev sandbox |
| Android JVM unit tests (receipts, wallet, budget, protected-app filter: 23) | **Compiled and passing** in the sandbox with `kotlinc` + JUnit against `android.jar` (not via Gradle) |
| Non-Compose Android code (`Usage`, `Settings`, `StationClient`, `MonitorService`, `BootReceiver`) | Type-checked with `kotlinc` against `android.jar` |
| Compose UI (`MainActivity`, `GateActivity`), `MainViewModel`, Gradle/AGP build, **APK** | **NOT built.** The sandbox cannot reach Google's Maven repository, so Gradle could not run. The GitHub Actions workflow is the first real build; until it is green, treat the APK as unbuilt. |
| Anything on a physical phone / Arduino UNO Q | **NOT tested** |

## Build
CI (`.github/workflows/ci.yml`) runs station tests, `./gradlew testDebugUnitTest assembleDebug` (JDK 17, Gradle 8.9 wrapper,
AGP 8.7.3, Kotlin 2.0.21, compile/target SDK 34, min SDK 26) and uploads the **`commonground-debug-apk`** artifact
(Actions run page > Artifacts). Workflows from Copilot-authored pushes need a maintainer to click "Approve and run".

Locally:
```bash
cd station && pip install -r requirements-dev.txt && python -m pytest -q tests
cd ../android && ./gradlew --no-daemon testDebugUnitTest assembleDebug   # -> app/build/outputs/apk/debug/app-debug.apk
adb install -r app/build/outputs/apk/debug/app-debug.apk
```
Without adb: copy the APK to the phone and open it (allow "install unknown apps" for the file manager). It is a debug build.

## Tracking vs. enforcement vs. demo
- **Tracking** – with the user-granted *Usage access*, today's foreground time of the **selected** apps is read through
  `UsageStatsManager`. Nothing is blocked. Without the permission the Budget tab says so and no usage is shown.
- **Enforcement** – opt-in, off by default, only possible while Usage access is granted. A visible foreground-service
  notification ("budget monitor is on", with a Stop button) appears; every 5 s it checks the foreground app. Only when
  the allowance is used up **and** a selected, non-protected app is in front does it show the soft gate (over the app if
  the optional *Display over other apps* permission was granted, otherwise as a notification). **Continue anyway** (10 min
  override) is always visible; the switch or Stop button turns it off. If Usage access is revoked the monitor switches
  itself off and says so. After a reboot it restarts only if the gate was enabled and permission still exists. Android
  may stop the service under aggressive battery management; that is accepted (this is not a lock).
- **Demo** – "Preview gate screen" shows the gate UI with a red *DEMO PREVIEW – nothing is being blocked* banner.
- Never gated: apps not selected; system apps and phone/contacts/SMS/messaging/maps/camera/settings/accessibility/
  emergency-like packages and the default dialer/SMS app are not offered and are filtered again at enforcement time.

## First-phone validation procedure
Needs a laptop (station) and an Android 8+ phone on the same Wi-Fi/hotspot. Internet is not required.

1. **Install** the debug APK (above). Open it; allow notifications if asked.
2. **Start the station** on the laptop: `cd station && pip install -r requirements.txt && CG_DEMO_MODE=true uvicorn app.main:app_factory --factory --host 0.0.0.0 --port 8000`. Connect the phone to the same network and note the laptop IP (e.g. 192.168.43.5). Open `http://<ip>:8000/api/status` in the phone browser: JSON appears.
3. **Pair**: in the phone browser open `http://<ip>:8000`, join with a nickname, Battery tab > *Pair Android app* (6-digit code, 5 min, single use). In the app: Station tab, enter `<ip>:8000` and the code, *Pair*. Expect "Paired with …". Reusing the code must fail.
4. **Quest**: web Quests tab, start a quest, wait 10 s, *Complete* → "+5 credits".
5. **Sync & verify**: app Battery tab > *Sync receipts*. Expect "1 new receipt(s), 1 redeemed", +5 min and a history row. Sync again: 0 new. Editing one character of a pasted receipt must say "Invalid receipt signature".
6. **Offline**: turn off the station or Wi-Fi (airplane mode). Battery tab, balance and history still load. Pasting a *new* receipt works offline and shows "not yet synced" until the next sync.
7. **Usage access**: Budget tab shows *NOT GRANTED*; tap *Open Usage access settings*, allow CommonGround, return: *GRANTED*. On the Apps tab select e.g. Instagram, use it for a couple of minutes, reopen the app: "Used today" rises. Revoke the permission again: the app must say so rather than show stale data.
8. **Gate**: set a small daily cap (5 min) and have credits; enable the soft gate (notification appears). Use the selected app past the allowance: the gate (or notification, if overlay not granted) appears. Test *Continue anyway* (no gate for 10 min) and *Go outside*. Confirm an unselected app and the dialer are never gated. Turn the switch off and confirm the notification disappears.
9. **Persistence**: force-stop and reopen the app; restart the station (same `station/data/`). Balance/history persist; *Sync* works again without re-pairing, and previously issued receipts still verify (same key file). Reboot the phone with the gate enabled and confirm the notification returns (Android 14+/OEM restrictions may prevent this — record the result).
10. **Phone browser**: run `docs/PHONE_BROWSER_CHECKLIST.md` on the real phone browser and note layout/playback problems.

Record device model, Android version, and the result of each step.

## Security model (summary; details in README)
- The station's ECDSA P-256 **private key stays in `receipt_key.pem`** (mode 0600, never served or returned by any API). The app stores only the **public key** and the station id derived from it.
- A receipt (`v:2`) is signed JSON with `id`, `user` (owner), `amount`, `aud` (station id = hash of its public key), `iat`, `exp` (default 30 days). The phone verifies signature, audience, owner and expiry offline when *adding* it; minutes already in the wallet do not expire.
- Receipts are **bearer-style but owner-bound on the server**: `GET /api/receipts` lists only the caller's; `POST /api/receipts/redeem` requires the caller's token and 403s for another user's receipt; redemption is one atomic SQL update (concurrent attempts: exactly one 200). The wallet also de-duplicates by receipt id. Someone who steals a receipt *and* a device token of the owner could redeem it.
- Pairing codes: random, 5-minute expiry, removed under a lock when claimed (single-use, race-safe). Brute force is limited per client IP (5 failures/min) plus a global ceiling (300 failures/10 min), so one client cannot lock everyone out; a LAN attacker with many IPs could still force the ceiling and delay pairing (a nuisance, not a credential leak).
- Device tokens: 192-bit random, stored hashed on the station, no expiry; revoke with `DELETE /api/devices/{id}` (list via `GET /api/devices`) or the app's *Unpair*, which calls `DELETE /api/devices/current`. A device token has the same powers as the web session of its user. The phone keeps its token in app-private storage (backups disabled), not in the Keystore.
- Transport is plain HTTP on the local network (no TLS certificate); a passive LAN attacker can read session tokens. Receipt integrity does not depend on transport.
