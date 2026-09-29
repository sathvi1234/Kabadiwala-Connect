import math
import secrets
from datetime import datetime, timezone

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.models import AuditLog, Material, User, utcnow


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def parse_dt(value: str | datetime | None) -> datetime:
    if value is None:
        return now()
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    text = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def audit(db: Session, actor: User | None, action: str, entity_type: str, entity_id: str, detail: dict | None = None, request: Request | None = None):
    ip = ""
    if request and request.client:
        ip = request.client.host or ""
    db.add(
        AuditLog(
            actor_id=actor.id if actor else None,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            detail=detail or {},
            ip=ip,
            created_at=utcnow(),
        )
    )


def material_by_code(db: Session, code: str) -> Material:
    mat = db.query(Material).filter(Material.code == code).one_or_none()
    if not mat:
        raise HTTPException(status_code=422, detail={"code": "unknown_material"})
    return mat


def public_code(prefix: str) -> str:
    stamp = now().strftime("%Y%m%d")
    return f"{prefix}-{stamp}-{secrets.token_hex(2).upper()}"


def money(value: float) -> float:
    return round(float(value) + 1e-9, 2)


def notify(db: Session, user_id: str, title: str, body: str, kind: str = "info", data: dict | None = None):
    from app.models import Notification

    db.add(Notification(user_id=user_id, title=title, body=body, kind=kind, data=data or {}, created_at=utcnow()))
