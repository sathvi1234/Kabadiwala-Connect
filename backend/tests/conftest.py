import io
import os
import tempfile
from pathlib import Path

_root = Path(tempfile.mkdtemp(prefix="kabadi-test-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_root / 'test.db').as_posix()}"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["ENV"] = "development"
os.environ["UPLOAD_DIR"] = str(_root / "uploads")
os.environ["OTP_DEV_CODE"] = "123456"
os.environ["CORS_ORIGINS"] = "http://localhost:5173"

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from seed import seed

seed()


def _png(color=(0, 180, 40)) -> bytes:
    image = Image.new("RGB", (64, 64), color)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


import pytest


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def collector_token(client):
    res = client.post("/api/auth/login", json={"phone": "9000000001", "password": "Demo@123"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["user"]["role"] == "collector"
    return body["token"]


@pytest.fixture(scope="session")
def recycler_token(client):
    res = client.post("/api/auth/login", json={"phone": "9000000011", "password": "Demo@123"})
    assert res.status_code == 200
    assert res.json()["user"]["role"] == "recycler"
    return res.json()["token"]


@pytest.fixture(scope="session")
def admin_token(client):
    res = client.post("/api/auth/login", json={"phone": "9999999999", "password": "Demo@123"})
    assert res.status_code == 200
    assert res.json()["user"]["role"] == "admin"
    return res.json()["token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
