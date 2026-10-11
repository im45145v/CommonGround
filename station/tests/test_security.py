import threading

from conftest import join
from app import receipts


def earn(client, clock, h, quest=1):
    run = client.post(f"/api/quests/{quest}/start", headers=h).json()
    clock.t += 10
    return client.post(f"/api/runs/{run['run_id']}/complete", headers=h).json()["receipt"]


def pair(client, h):
    code = client.post("/api/pair/code", headers=h).json()["code"]
    r = client.post("/api/pair/claim", json={"code": code, "label": "phone"})
    assert r.status_code == 200
    return r.json(), {"Authorization": "Bearer " + r.json()["token"]}


def test_private_key_never_in_api_responses(client):
    h, _ = join(client)
    claim, _ = pair(client, h)
    blob = str(client.get("/api/pair", headers=h).json()) + str(claim) + str(client.get("/api/status").json())
    assert "PRIVATE" not in blob and "BEGIN" not in blob
    assert client.get("/receipt_key.pem").status_code == 404
    assert client.get("/static/../receipt_key.pem").status_code == 404


def test_receipt_payload_has_audience_and_expiry(client, clock):
    h, u = join(client)
    p = receipts.verify(client.app.state.svc.key, earn(client, clock, h))
    assert p["v"] == 2 and p["aud"] == receipts.station_id(client.app.state.svc.key)
    assert p["exp"] == p["iat"] + 30 * 86400


def test_cannot_redeem_or_list_other_users_receipts(client, clock):
    a, _ = join(client, "alice")
    b, _ = join(client, "bob")
    token = earn(client, clock, a)
    assert client.post("/api/receipts/redeem", json={"receipt": token}).status_code == 401
    assert client.post("/api/receipts/redeem", json={"receipt": token}, headers=b).status_code == 403
    assert client.get("/api/receipts", headers=b).json()["receipts"] == []
    assert client.get("/api/receipts", headers=a).json()["receipts"] == [token]
    assert client.post("/api/receipts/redeem", json={"receipt": token}, headers=a).status_code == 200  # still redeemable by owner


def test_receipt_from_another_station_rejected(make_client, clock):
    c1, c2 = make_client(), make_client()
    h1, _ = join(c1)
    token = earn(c1, clock, h1)
    h2, _ = join(c2)
    assert c2.post("/api/receipts/verify", json={"receipt": token}).status_code == 422
    assert c2.post("/api/receipts/redeem", json={"receipt": token}, headers=h2).status_code == 422


def test_expired_receipt_cannot_be_redeemed_or_synced(client, clock):
    h, _ = join(client)
    token = earn(client, clock, h)
    clock.t += 31 * 86400
    assert client.post("/api/receipts/redeem", json={"receipt": token}, headers=h).status_code == 410
    assert client.get("/api/receipts", headers=h).json()["receipts"] == []
    assert client.post("/api/receipts/verify", json={"receipt": token}).json()["expired"] is True


def test_concurrent_redeem_succeeds_exactly_once(client, clock):
    h, _ = join(client)
    token = earn(client, clock, h)
    codes = []

    def go():
        codes.append(client.post("/api/receipts/redeem", json={"receipt": token}, headers=h).status_code)

    ts = [threading.Thread(target=go) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert sorted(codes) == [200] + [409] * 7


def test_pair_code_single_use_and_concurrent_claim(client):
    h, _ = join(client)
    code = client.post("/api/pair/code", headers=h).json()["code"]
    out = []

    def go():
        out.append(client.post("/api/pair/claim", json={"code": code}).status_code)

    ts = [threading.Thread(target=go) for _ in range(6)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert sorted(out) == [200] + [422] * 5
    assert len(client.get("/api/devices", headers=h).json()) == 1


def test_lockout_is_per_client_not_global_dos(client, clock):
    svc = client.app.state.svc
    h, _ = join(client)
    from app.services import ServiceError
    import pytest
    for _ in range(5):
        with pytest.raises(ServiceError) as e:
            svc.claim_pair_code("000000", "x", client="attacker")
        assert e.value.status == 422
    with pytest.raises(ServiceError) as e:
        svc.claim_pair_code("000000", "x", client="attacker")
    assert e.value.status == 429
    # a legitimate client is unaffected
    code = svc.create_pair_code({"id": "u"})["code"] if False else client.post("/api/pair/code", headers=h).json()["code"]
    assert svc.claim_pair_code(code, "phone", client="friend")["token"]
    # attacker's lockout ends after a minute
    clock.t += 61
    with pytest.raises(ServiceError) as e:
        svc.claim_pair_code("000000", "x", client="attacker")
    assert e.value.status == 422


def test_global_ceiling_blocks_distributed_guessing(client):
    svc = client.app.state.svc
    from app.services import ServiceError
    import pytest
    for i in range(svc.CLAIM_GLOBAL_MAX):
        with pytest.raises(ServiceError):
            svc.claim_pair_code("000000", "x", client=f"c{i}")
    with pytest.raises(ServiceError) as e:
        svc.claim_pair_code("000000", "x", client="new")
    assert e.value.status == 429


def test_device_revocation(client, clock):
    h, _ = join(client)
    other, _ = join(client, "bob")
    _, dev = pair(client, h)
    assert client.get("/api/wallet", headers=dev).status_code == 200
    dev_id = client.get("/api/devices", headers=h).json()[0]["id"]
    assert client.delete(f"/api/devices/{dev_id}", headers=other).status_code == 404  # not yours
    assert client.delete(f"/api/devices/{dev_id}", headers=h).status_code == 200
    assert client.get("/api/wallet", headers=dev).status_code == 401
    _, dev2 = pair(client, h)
    assert client.delete("/api/devices/current", headers=dev2).status_code == 200
    assert client.get("/api/wallet", headers=dev2).status_code == 401


def test_tokens_are_stored_hashed(client):
    h, u = join(client)
    claim, _ = pair(client, h)
    db = client.app.state.svc.db
    for tok in (u["token"], claim["token"]):
        assert not db.query("SELECT 1 FROM users WHERE token_hash=?", (tok,))
        assert not db.query("SELECT 1 FROM device_tokens WHERE token_hash=?", (tok,))
