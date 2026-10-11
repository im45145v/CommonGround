import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402


class Clock:
    def __init__(self):
        self.t = 1_700_000_000.0

    def __call__(self):
        return self.t


class FakeAI:
    def __init__(self, reply=None, fail=False):
        self.reply, self.fail = reply, fail

    def complete(self, prompt):
        if self.fail:
            raise TimeoutError()
        return self.reply


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def make_client(tmp_path, clock):
    def _make(provider=None, **kw):
        s = Settings(db_path=":memory:", media_dir=str(Path(__file__).resolve().parent.parent / "media"),
                     demo_mode=True, demo_quest_seconds=10, daily_limit=20,
                     shared_bonus=2, ai_enabled=False, trivia_seconds=1, **kw)
        return TestClient(create_app(s, provider=provider, clock=clock))
    return _make


@pytest.fixture
def client(make_client):
    return make_client()


def join(client, name="alice"):
    j = client.post("/api/session", json={"nickname": name}).json()
    return {"Authorization": "Bearer " + j["token"]}, j
