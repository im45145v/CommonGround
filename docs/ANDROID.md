# Android companion: build, install, and end-to-end test

> **Verification status.** The wallet, receipt-verification and budget logic (`ReceiptVerifier.kt`, `Wallet.kt`,
> `Budget.kt`) have JVM unit tests that were run (17 tests pass), including verifying receipts signed by the real
> Python station. The Compose UI, `UsageStatsManager` tracking, the monitor service and the gate were **not compiled
> or run** in the development sandbox (the Android Gradle plugin could not be downloaded there). They must be built
> and tested on a real phone; CI (`.github/workflows/ci.yml`) builds the APK and runs the unit tests. Expect to fix small
> compile errors the first time you build.

## Build and install
Requirements: Android Studio (Koala+) or JDK 17 + Android SDK 34; a phone with Android 8.0+ (API 26) and USB debugging.

```bash
cd android
./gradlew testDebugUnitTest        # JVM unit tests (receipts, wallet, budget)
./gradlew assembleDebug            # app/build/outputs/apk/debug/app-debug.apk
adb install -r app/build/outputs/apk/debug/app-debug.apk
```
(Or open `android/` in Android Studio, pick the phone, press Run.) Enable *Developer options > USB debugging* first.

## What the app does
- **Battery tab:** remaining minutes today, total earned, reward history, "Sync", and paste-a-receipt (offline).
- **Station tab:** enter the station URL and the 6-digit pairing code. The app stores the station's **public** key.
- **Apps tab:** choose recreational apps. System apps, the default dialer/SMS app, and settings/emergency/
  accessibility-like packages are never offered, so they are never counted or gated.
- **Budget tab:** Usage-access permission status and onboarding, daily cap, opt-in gate, visible override, and a
  clearly labelled **demo** preview of the gate screen (blocks nothing).

1 credit = 1 minute of recreational time (`Wallet.minutesPerCredit`). Allowance today = min(daily cap, minutes earned
minus minutes used on previous days).

### Tracking vs. enforcement (be clear about which is which)
- **Tracking** (always, once you grant *Usage access*): reads today's foreground time for your selected apps via
  `UsageStatsManager`. Nothing is blocked. Without the permission the app says so and shows no usage.
- **Enforcement** (opt-in, off by default): a visible foreground-service notification is shown while a monitor checks the
  foreground app every 5 s. When your allowance is used up and a selected app is open it shows the soft gate. The gate
  can appear over the app only if you additionally grant "Display over other apps"; otherwise you get a heads-up
  notification that opens the gate. "Continue anyway" (10 min override) is always visible, and the switch (or the
  notification's Stop button) turns the monitor off. Android may stop background services on aggressive battery
  savers; it is not a lock and is not designed to be tamper-proof.
- **Demo gate** ("Preview gate screen"): only displays the screen.

## End-to-end test without internet
Needs: the station (laptop for now, UNO Q later) and the Android phone on the **same local network with no internet** —
e.g. a phone hotspot/travel router, or a laptop with Wi-Fi sharing. (Whether the UNO Q can host its own access point
is unverified.) If the phone's Wi-Fi says "no internet", keep it connected; Android may route only the station
subnet over Wi-Fi, which is what we want.

1. On the station machine: `cd station && pip install -r requirements.txt && CG_DEMO_MODE=true uvicorn app.main:app_factory --factory --host 0.0.0.0 --port 8000`. Note its LAN IP (e.g. 192.168.43.5).
2. Phone browser: `http://192.168.43.5:8000`, choose a nickname.
3. Web **Battery** tab > **Pair Android app** shows a 6-digit code (valid 5 minutes, single use).
4. Android app > **Station** tab: URL `192.168.43.5:8000`, enter the code, tap **Pair**. Expect "Paired with …".
5. Web **Quests** tab: start a quest, wait 10 s (demo), tap **Complete** → "+5 credits".
6. Android **Battery** tab > **Sync receipts**. Expect "1 new receipt(s)", +5 min, a history row. The app verified the
   ECDSA signature locally and redeemed the receipt on the station.
7. Sync again → "0 new". Tap-add the same receipt manually → "already in your wallet". (Duplicate protection.)
8. Switch the station off / enable airplane mode: the Battery tab, history and balance still work (stored in
   `files/wallet.json`). Force-stop and reopen the app: data is still there.
9. Budget tab: grant Usage access (Settings opens; allow CommonGround), select e.g. Instagram on the Apps tab, use it,
   then check that "Used today" rises. Optional: set a 1–5 minute cap, enable the gate, and use the app past the allowance
   to see the gate/notification; test **Continue anyway** and the switch-off.
10. Forgery check (optional): editing any character of a pasted receipt must give "Invalid receipt signature".

## Needs a physical device (not yet tested)
Everything in the UI, usage-stats accuracy, the permission flows, the foreground service on your Android version
(Android 14 requires the special-use foreground-service declaration already in the manifest), the overlay/notification gate,
and real-network pairing.
