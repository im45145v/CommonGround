# Manual phone-browser test checklist (station web app)

**Status: NOT YET RUN on a physical device.** Mobile responsiveness is unverified until someone ticks this list.
Record: phone model, OS, browser, station URL, date, tester.

Setup: phone on the same network as the station, open `http://<station-ip>:8000`; try portrait and landscape,
and a small (~360 px) and large phone if possible.

- [ ] Page loads with no internet; header shows station name and "works offline".
- [ ] No horizontal scrolling; text readable without zoom; tap targets comfortable.
- [ ] Join with a nickname; reload the page — you stay joined.
- [ ] Quests tab: start a quest, join-code field usable with the on-screen keyboard; Complete after 10 s awards credits; too-early Complete shows a message.
- [ ] Two phones: second phone starts the same quest with the first phone's code; both receive the shared bonus.
- [ ] Battery tab: balance/history correct; **Pair Android app** shows a 6-digit code.
- [ ] Trivia: two phones join the same room, start, answer; scores update; game over screen shown.
- [ ] Talk tab: send a message, see it on another phone; report and block work; new AI question appears.
- [ ] Library: music plays (and seeks) in the mobile browser, a book opens as text, cached audio plays.
- [ ] Radio tab shows an announcement (source labelled `fallback` or `gemma`).
- [ ] Turn the station's internet off (or use a no-internet hotspot): everything above still works.
- [ ] Note any layout problems with screenshots.
