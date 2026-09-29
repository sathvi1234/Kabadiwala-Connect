"""Vercel serverless entry. Same-origin FastAPI app with a writable SQLite file in /tmp."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

os.environ["ENV"] = "production"
os.environ["DEMO_MODE"] = "true"
os.environ["DATABASE_URL"] = "sqlite:////tmp/kabadiwala.db"
os.environ["UPLOAD_DIR"] = "/tmp/uploads"
os.environ["JWT_SECRET"] = "kabadiwala-connect-demo-jwt-secret-32b"
os.environ["SEED_HISTORY_DAYS"] = "90"
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")
Path("/tmp/uploads").mkdir(parents=True, exist_ok=True)

from app.blob_sync import pull, push  # noqa: E402

remote = pull()

from app.database import Base, SessionLocal, engine, ensure_columns  # noqa: E402
from app.models import User  # noqa: E402

ensure_columns()
Base.metadata.create_all(engine)
db = SessionLocal()
needs_seed = db.query(User).first() is None
db.close()
if needs_seed and remote in {"missing", "disabled"}:
    from seed import seed

    seed()
    push()

from app.main import app  # noqa: E402


@app.middleware("http")
async def share_database(request, call_next):
    pull()
    try:
        return await call_next(request)
    finally:
        push()


@app.middleware("http")
async def restore_vercel_path(request, call_next):
    """Keep FastAPI routes on the browser path when Vercel rewrites to this function."""
    path = request.scope.get("path") or ""
    if path in {"/api/index", "/api/index.py"}:
        original = request.headers.get("x-forwarded-uri") or request.headers.get("x-invoke-path") or ""
        restored = original.split("?", 1)[0]
        if restored.startswith("/"):
            request.scope["path"] = restored
            request.scope["raw_path"] = restored.encode()
    return await call_next(request)
