from conftest import join
from app import receipts


def run_quest(client, clock, h, quest=1, code=None):
    r = client.post(f"/api/quests/{quest}/start", json={"join_code": code}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def test_status_and_quests(client):
    assert client.get("/api/status").json()["online_required"] is False
    assert len(client.get("/api/quests").json()) >= 3
    assert client.get("/").status_code == 200


def test_auth_required(client):
    assert client.get("/api/wallet").status_code == 401
    assert client.post("/api/quests/1/start").status_code == 401


def test_quest_completion_and_receipt(client, clock):
    h, u = join(client)
    run = run_quest(client, clock, h)
    early = client.post(f"/api/runs/{run['run_id']}/complete", headers=h)
    assert early.status_code == 425
    assert client.get("/api/wallet", headers=h).json()["balance"] == 0
    clock.t += 10
    done = client.post(f"/api/runs/{run['run_id']}/complete", headers=h).json()
    assert done["credits"] == 5
    payload = receipts.verify("test-secret", done["receipt"])
    assert payload["amount"] == 5 and payload["user"] == u["user_id"]
    w = client.get("/api/wallet", headers=h).json()
    assert w["balance"] == 5 and w["history"][0]["amount"] == 5
    # duplicate completion is rejected, no extra credit
    assert client.post(f"/api/runs/{run['run_id']}/complete", headers=h).status_code == 409
    assert client.get("/api/wallet", headers=h).json()["balance"] == 5


def test_cannot_complete_someone_elses_run(client, clock):
    h, _ = join(client)
    h2, _ = join(client, "bob")
    run = run_quest(client, clock, h)
    clock.t += 10
    assert client.post(f"/api/runs/{run['run_id']}/complete", headers=h2).status_code == 404


def test_shared_bonus(client, clock):
    h, _ = join(client)
    h2, _ = join(client, "bob")
    a = run_quest(client, clock, h)
    b = run_quest(client, clock, h2, code=a["code"])
    assert b["shared"]
    clock.t += 10
    assert client.post(f"/api/runs/{a['run_id']}/complete", headers=h).json()["credits"] == 7
    assert client.post(f"/api/runs/{b['run_id']}/complete", headers=h2).json()["credits"] == 7


def test_cannot_join_own_run_or_wrong_quest(client, clock):
    h, _ = join(client)
    h2, _ = join(client, "bob")
    a = run_quest(client, clock, h, quest=1)
    assert client.post("/api/quests/1/start", json={"join_code": a["code"]}, headers=h).status_code == 409
    assert client.post("/api/quests/2/start", json={"join_code": a["code"]}, headers=h2).status_code == 422


def test_daily_limit(client, clock):
    h, _ = join(client)
    total = 0
    for _ in range(6):  # 5 credits each, limit 20
        run = run_quest(client, clock, h)
        clock.t += 10
        total += client.post(f"/api/runs/{run['run_id']}/complete", headers=h).json()["credits"]
    assert total == 20
    assert client.get("/api/wallet", headers=h).json()["balance"] == 20
    # next day resets
    clock.t += 86400
    run = run_quest(client, clock, h)
    clock.t += 10
    assert client.post(f"/api/runs/{run['run_id']}/complete", headers=h).json()["credits"] == 5


def test_receipt_verify_and_single_redeem(client, clock):
    h, _ = join(client)
    run = run_quest(client, clock, h)
    clock.t += 10
    token = client.post(f"/api/runs/{run['run_id']}/complete", headers=h).json()["receipt"]
    assert client.post("/api/receipts/verify", json={"receipt": token}).json()["valid"]
    assert client.post("/api/receipts/redeem", json={"receipt": token}).status_code == 200
    assert client.post("/api/receipts/redeem", json={"receipt": token}).status_code == 409


def test_tampered_receipt_rejected(client):
    forged = receipts.sign("wrong-key", {"id": "x", "user": "u", "amount": 999})
    assert client.post("/api/receipts/verify", json={"receipt": forged}).status_code == 422
    valid_sig_unknown = receipts.sign("test-secret", {"id": "x", "user": "u", "amount": 999})
    assert client.post("/api/receipts/verify", json={"receipt": valid_sig_unknown}).status_code == 422
    assert client.post("/api/receipts/verify", json={"receipt": "garbage"}).status_code == 422


def test_receipt_roundtrip_unit():
    t = receipts.sign("k", {"a": 1})
    assert receipts.verify("k", t) == {"a": 1}
    head, sig = t.split(".")
    assert receipts.verify("k", head + "." + sig[:-2] + "AA") is None
