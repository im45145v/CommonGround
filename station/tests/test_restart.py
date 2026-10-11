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
    assert c1.post("/api/receipts/redeem", json={"receipt": token}).status_code == 200

    c2 = make(tmp_path, clock)  # restart: same DB + key file
    pub2 = c2.get("/api/pair", headers={"Authorization": h["Authorization"]}).json()["public_key"]
    assert pub1 == pub2
    assert receipts.verify(receipts.load_public_key(pub2), token)  # old receipt still verifies
    assert c2.post("/api/receipts/verify", json={"receipt": token}).json()["redeemed"] is True
    assert c2.post("/api/receipts/redeem", json={"receipt": token}).status_code == 409  # still no duplicates


def test_key_file_is_private(tmp_path):
    k = receipts.load_or_create_key(str(tmp_path / "k.pem"))
    assert (Path(tmp_path) / "k.pem").stat().st_mode & 0o077 == 0
    k2 = receipts.load_or_create_key(str(tmp_path / "k.pem"))
    assert receipts.public_key_b64(k) == receipts.public_key_b64(k2)


def test_phone_cannot_forge_with_public_key(client):
    pub = receipts.load_public_key(client.app.state.svc.public_key)
    assert not hasattr(pub, "sign")
