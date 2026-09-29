"""Keep the SQLite file in Vercel Blob so every serverless instance shares one database."""

import hashlib
import os
import threading
from pathlib import Path

import httpx

PATHNAME = "kabadiwala.db"
API = "https://vercel.com/api/blob"
_lock = threading.Lock()
_hash: str | None = None


def enabled() -> bool:
    return bool(os.environ.get("BLOB_READ_WRITE_TOKEN"))


def _headers(extra: dict | None = None) -> dict[str, str]:
    headers = {
        "authorization": f"Bearer {os.environ['BLOB_READ_WRITE_TOKEN']}",
        "x-api-version": "12",
    }
    if extra:
        headers.update(extra)
    return headers


def _db_path() -> Path:
    url = os.environ.get("DATABASE_URL", "")
    if url.startswith("sqlite:///"):
        return Path(url.removeprefix("sqlite:///"))
    return Path("/tmp/kabadiwala.db")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pull() -> str:
    """Download the shared database. Returns missing, updated, same, error, or disabled."""
    global _hash
    if not enabled():
        return "disabled"
    with _lock:
        try:
            with httpx.Client(timeout=20) as client:
                listed = client.get(API, params={"prefix": PATHNAME, "limit": "10"}, headers=_headers())
                if listed.status_code >= 400:
                    return "error"
                blobs = listed.json().get("blobs") or []
                match = next((item for item in blobs if item.get("pathname") == PATHNAME), None)
                if match is None:
                    return "missing"
                downloaded = client.get(match["url"], headers=_headers())
                if downloaded.status_code >= 400:
                    return "error"
                data = downloaded.content
        except Exception:
            return "error"
        digest = _digest(data)
        path = _db_path()
        if digest == _hash and path.exists():
            return "same"
        _replace(data, digest)
        return "updated"


def push() -> None:
    global _hash
    if not enabled():
        return
    path = _db_path()
    if not path.exists():
        return
    with _lock:
        _checkpoint()
        data = path.read_bytes()
        digest = _digest(data)
        if digest == _hash:
            return
        try:
            with httpx.Client(timeout=40) as client:
                response = client.put(
                    f"{API}/",
                    params={"pathname": PATHNAME},
                    content=data,
                    headers=_headers(
                        {
                            "x-content-type": "application/octet-stream",
                            "x-vercel-blob-access": "private",
                            "x-add-random-suffix": "0",
                            "x-allow-overwrite": "1",
                        }
                    ),
                )
            if response.status_code < 400:
                _hash = digest
        except Exception:
            return


def _replace(data: bytes, digest: str) -> None:
    global _hash
    try:
        from app.database import engine

        engine.dispose()
    except Exception:
        pass
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    _hash = digest


def _checkpoint() -> None:
    try:
        from app.database import engine

        with engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)")
    except Exception:
        pass
