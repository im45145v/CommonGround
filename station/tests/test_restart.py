from pathlib import Path

from fastapi.testclient import TestClient

from app import receipts
from app.config import Settings
from app.main import create_app
from conftest import join


def make(tmp_path, clock):
    s = Settings(db_path=str(tmp_path / "s.db"), media_dir=str(tmp_path), demo_mode=True, demo_quest_seconds=10,
                 ai_enabled=False)
    return TestClient(create_app(s, clock=clock))


def test_key_and_receipts_survive_restart(tmp_path, clock):
    c1 = make(tmp_path, clock)
    h, u = join(c1)
    pub1 = c1.get("/api/pair", headers=h).json()["public_key"]
    run = c1.post("/api/quests/1/start", headers=h).json()
    clock.t += 10
    token = c1.post(f"/api/runs/{run['run_id']}/complete", headers=h).json()["receipt"]
    assert c1.post("/api/receipts/redeem", json={"receipt": token}, headers=h).status_code == 200

    c2 = make(tmp_path, clock)  # restart: same DB + key file
    pub2 = c2.get("/api/pair", headers={"Authorization": h["Authorization"]}).json()["public_key"]
    assert pub1 == pub2
    assert receipts.verify(receipts.load_public_key(pub2), token)  # old receipt still verifies
    assert c2.post("/api/receipts/verify", json={"receipt": token}).json()["redeemed"] is True
    assert c2.post("/api/receipts/redeem", json={"receipt": token}, headers=h).status_code == 409  # still no duplicates


def test_key_file_is_private(tmp_path):
    k = receipts.load_or_create_key(str(tmp_path / "k.pem"))
    assert (Path(tmp_path) / "k.pem").stat().st_mode & 0o077 == 0
    k2 = receipts.load_or_create_key(str(tmp_path / "k.pem"))
    assert receipts.public_key_b64(k) == receipts.public_key_b64(k2)


def test_phone_cannot_forge_with_public_key(client):
    pub = receipts.load_public_key(client.app.state.svc.public_key)
    assert not hasattr(pub, "sign")


def test_pairing_and_receipt_sync(client, clock):
    h, u = join(client)
    code = client.post("/api/pair/code", headers=h).json()["code"]
    claim = client.post("/api/pair/claim", json={"code": code, "label": "pixel"}).json()
    assert claim["user_id"] == u["user_id"] and claim["public_key"] and "private" not in str(claim).lower()
    assert client.post("/api/pair/claim", json={"code": code}).status_code == 422  # single use
    dev = {"Authorization": "Bearer " + claim["token"]}
    run = client.post("/api/quests/1/start", headers=h).json()
    clock.t += 10
    token = client.post(f"/api/runs/{run['run_id']}/complete", headers=h).json()["receipt"]
    assert client.get("/api/receipts", headers=dev).json()["receipts"] == [token]
    assert client.get("/api/wallet", headers=dev).json()["balance"] == 5
    assert client.post("/api/receipts/redeem", json={"receipt": token}, headers=h).status_code == 200
    assert client.get("/api/receipts", headers=dev).json()["receipts"] == []


def test_pair_code_expires(client, clock):
    h, _ = join(client)
    code = client.post("/api/pair/code", headers=h).json()["code"]
    clock.t += 301
    assert client.post("/api/pair/claim", json={"code": code}).status_code == 422
    assert client.post("/api/pair/code").status_code == 401


