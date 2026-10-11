import json

from conftest import FakeAI, join


def test_ai_fallback_on_failure_and_malformed(make_client):
    for prov in (None, FakeAI(fail=True), FakeAI(reply="not json"), FakeAI(reply='{"title": "x"}')):
        c = make_client(provider=prov)
        h, _ = join(c)
        r = c.post("/api/ai/quest", headers=h).json()
        assert r["source"] == "fallback" and r["title"]


def test_ai_success_creates_server_rewarded_quest(make_client):
    c = make_client(provider=FakeAI(reply=json.dumps({"title": "Moss hunt", "description": "Find moss", "reward": 9999})))
    h, _ = join(c)
    r = c.post("/api/ai/quest", headers=h).json()
    assert r["source"] == "gemma"
    q = [x for x in c.get("/api/quests").json() if x["id"] == r["quest_id"]][0]
    assert q["reward"] == 5


def test_radio_and_discussion(client):
    h, _ = join(client)
    assert client.post("/api/radio", headers=h).json()["script"]
    q = client.post("/api/ai/discussion", headers=h).json()["question"]
    assert any(m["body"] == q for m in client.get("/api/talk", headers=h).json())


def test_talk_report_block(client):
    a, ua = join(client)
    b, ub = join(client, "bob")
    mid = client.post("/api/talk", json={"body": "hello"}, headers=a).json()["id"]
    assert any(m["id"] == mid for m in client.get("/api/talk", headers=b).json())
    client.post("/api/block", json={"user_id": ua["user_id"]}, headers=b)
    assert not any(m["id"] == mid for m in client.get("/api/talk", headers=b).json())
    assert any(m["id"] == mid for m in client.get("/api/talk", headers=a).json())
    for i in range(3):
        h, _ = join(client, f"r{i}")
        client.post("/api/report", json={"message_id": mid}, headers=h)
    assert not any(m["id"] == mid for m in client.get("/api/talk", headers=a).json())
    assert client.post("/api/block", json={"user_id": ua["user_id"]}, headers=a).status_code == 422


def test_library(client):
    assert client.get("/api/library/music").json()
    assert client.get("/api/library/books").json()
    r = client.get("/api/library/music/garden_chime.wav")
    assert r.status_code == 200 and r.content[:4] == b"RIFF"
    assert client.get("/api/library/music/..%2F..%2Fapp%2Fmain.py").status_code == 404
    assert client.get("/api/library/secrets/x").status_code == 404


def test_pairing_returns_key(client):
    h, u = join(client)
    j = client.get("/api/pair", headers=h).json()
    assert j["user_id"] == u["user_id"] and j["key_algorithm"] == "ECDSA-P256-SHA256"
    assert "receipt_key" not in j and "BEGIN" not in str(j) and "PRIVATE" not in str(j)
    assert j["public_key"] == client.app.state.svc.public_key


def test_trivia_multiplayer(client):
    _, a = join(client, "alice")
    _, b = join(client, "bob")
    with client.websocket_connect(f"/ws/trivia/r1?token={a['token']}") as wa, \
            client.websocket_connect(f"/ws/trivia/r1?token={b['token']}") as wb:
        assert wa.receive_json()["type"] == "players"
        wa.receive_json(); wb.receive_json()  # both see the 2-player lobby
        wa.send_json({"type": "start"})
        for _ in range(5):
            qa, qb = wa.receive_json(), wb.receive_json()
            assert qa["type"] == "question" and qb["q"] == qa["q"]
            wa.send_json({"type": "answer", "choice": 0})
            wb.send_json({"type": "answer", "choice": "x"})  # invalid ignored
            ra = wa.receive_json(); wb.receive_json()
            assert ra["type"] == "result"
        end = wa.receive_json()
        assert end["type"] == "finished" and len(end["scores"]) == 2


def test_trivia_rejects_bad_token(client):
    import pytest
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/trivia/r1?token=nope"):
            pass


def test_hardware_events_recorded(client, clock):
    h, _ = join(client)
    run = client.post("/api/quests/1/start", headers=h).json()
    clock.t += 10
    client.post(f"/api/runs/{run['run_id']}/complete", headers=h)
    assert {"boot", "quest_started", "quest_completed"} <= set(client.app.state.display.events)
