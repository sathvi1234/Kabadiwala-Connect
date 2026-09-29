from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Badge, Notification, Tutorial, User, UserBadge
from app.security import get_current_user
from app.storage import absolute_path, upload_root

router = APIRouter(prefix="/api", tags=["inbox"])


@router.get("/notifications")
def notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Notification).filter(Notification.user_id == user.id).order_by(Notification.created_at.desc()).limit(50).all()
    return [
        {"id": r.id, "title": r.title, "body": r.body, "kind": r.kind, "read": r.read, "at": r.created_at.isoformat(), "data": r.data}
        for r in rows
    ]


@router.post("/notifications/{note_id}/read")
def read_note(note_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.get(Notification, note_id)
    if not row or row.user_id != user.id:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    row.read = True
    db.commit()
    return {"read": True}


@router.get("/tutorials")
def tutorials(lang: str = "en", db: Session = Depends(get_db)):
    rows = db.query(Tutorial).filter(Tutorial.lang == lang).order_by(Tutorial.feature_key.asc()).all()
    return [{"feature": r.feature_key, "title": r.title, "script": r.script, "lang": r.lang} for r in rows]


@router.get("/rewards")
def rewards(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    badges = db.query(Badge).order_by(Badge.threshold.asc()).all()
    owned = {b.badge_id for b in db.query(UserBadge).filter(UserBadge.user_id == user.id).all()}
    return {
        "referral_code": user.referral_code,
        "badges": [
            {"code": b.code, "name": b.name, "description": b.description, "threshold": b.threshold, "earned": b.id in owned}
            for b in badges
        ],
    }


@router.get("/files/{path:path}")
def files(path: str, user: User = Depends(get_current_user)):
    if ".." in path or path.startswith("/"):
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    full = absolute_path(path)
    root = upload_root().resolve()
    if not str(full.resolve()).startswith(str(root)) or not full.exists():
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    if path.startswith(("proofs/", "documents/")) and user.role != "admin":
        raise HTTPException(status_code=403, detail={"code": "forbidden"})
    return FileResponse(full)
