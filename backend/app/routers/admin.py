from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    AuditLog,
    Dispute,
    Lot,
    RecyclerDocument,
    RecyclerProfile,
    SyncQueueLog,
    Transaction,
    User,
    utcnow,
)
from app.security import deny_if_demo, require_roles
from app.services.common import audit, notify
from app.services.impact import impact

router = APIRouter(prefix="/api/admin", tags=["admin"])


def admin(user: User = Depends(require_roles("admin"))):
    return user


def _verified_pct(db: Session) -> float:
    total = db.query(Lot).count()
    if not total:
        return 0
    done = db.query(Lot).filter(Lot.status.in_(["handed_over", "processing", "completed"])).count()
    return round(100 * done / total, 1)


@router.get("/summary")
def summary(user: User = Depends(admin), db: Session = Depends(get_db)):
    start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return {
        "collectors": db.query(User).filter(User.role == "collector", User.is_active.is_(True)).count(),
        "recyclers": db.query(RecyclerProfile).filter(RecyclerProfile.status == "approved").count(),
        "pending_recyclers": db.query(RecyclerProfile).filter(RecyclerProfile.status == "pending").count(),
        "lots": db.query(Lot).count(),
        "lots_today": db.query(Lot).filter(Lot.created_at >= start).count(),
        "verified_handover_pct": _verified_pct(db),
        "open_disputes": db.query(Dispute).filter(Dispute.status == "open").count(),
        "paid": round(float(db.query(func.coalesce(func.sum(Transaction.paid_amount), 0)).scalar() or 0), 2),
        "impact": impact(db),
    }


@router.get("/recyclers")
def recycler_queue(status: str = "pending", user: User = Depends(admin), db: Session = Depends(get_db)):
    rows = db.query(RecyclerProfile, User).join(User, User.id == RecyclerProfile.user_id)
    if status:
        rows = rows.filter(RecyclerProfile.status == status)
    out = []
    for profile, account in rows.all():
        docs = db.query(RecyclerDocument).filter(RecyclerDocument.recycler_id == account.id).all()
        out.append(
            {
                "user_id": account.id,
                "name": account.name,
                "phone": account.phone,
                "business_name": profile.business_name,
                "licence_number": profile.licence_number,
                "address": profile.address,
                "city": profile.city,
                "materials": profile.materials,
                "status": profile.status,
                "rejection_reason": profile.rejection_reason,
                "documents": [{"id": d.id, "path": d.file_path, "type": d.doc_type} for d in docs],
            }
        )
    return out


@router.post("/recyclers/{user_id}/decision")
def decide(user_id: str, payload: dict, request: Request, user: User = Depends(admin), db: Session = Depends(get_db)):
    profile = db.query(RecyclerProfile).filter(RecyclerProfile.user_id == user_id).one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    decision = payload.get("decision")
    if decision not in {"approved", "rejected"}:
        raise HTTPException(status_code=422, detail={"code": "bad_decision"})
    reason = str(payload.get("reason", "")).strip()
    if decision == "rejected" and len(reason) < 3:
        raise HTTPException(status_code=422, detail={"code": "reason_required"})
    profile.status = decision
    profile.rejection_reason = reason if decision == "rejected" else None
    if decision == "approved":
        profile.availability = "available"
    audit(db, user, "recycler_verification", "recycler", user_id, {"decision": decision, "reason": reason}, request)
    notify(db, user_id, "Verification update", f"Your recycler account is {decision}.", "verification")
    db.commit()
    return {"status": profile.status}


@router.get("/users")
def users(role: str | None = None, user: User = Depends(admin), db: Session = Depends(get_db)):
    q = db.query(User)
    if role:
        q = q.filter(User.role == role)
    return [
        {"id": row.id, "name": row.name, "phone": row.phone, "role": row.role, "active": row.is_active, "language": row.preferred_language}
        for row in q.order_by(User.created_at.desc()).all()
    ]


@router.patch("/users/{user_id}")
def patch_user(user_id: str, payload: dict, request: Request, user: User = Depends(admin), db: Session = Depends(get_db)):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    if "is_active" in payload or "role" in payload:
        deny_if_demo(user)
    if "is_active" in payload:
        target.is_active = bool(payload["is_active"])
    if "role" in payload:
        if payload["role"] not in {"collector", "recycler", "admin"}:
            raise HTTPException(status_code=422, detail={"code": "bad_role"})
        target.role = payload["role"]
    audit(db, user, "user_update", "user", user_id, payload, request)
    db.commit()
    return {"id": target.id, "role": target.role, "active": target.is_active}


@router.get("/disputes")
def disputes(user: User = Depends(admin), db: Session = Depends(get_db)):
    from app.routers.trust import list_disputes

    return list_disputes(user, db)


@router.post("/disputes/{dispute_id}/resolve")
def resolve(dispute_id: str, payload: dict, request: Request, user: User = Depends(admin), db: Session = Depends(get_db)):
    row = db.get(Dispute, dispute_id)
    if not row:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    status = payload.get("status")
    if status not in {"resolved", "rejected", "under_review"}:
        raise HTTPException(status_code=422, detail={"code": "bad_status"})
    resolution = str(payload.get("resolution", "")).strip()
    if status in {"resolved", "rejected"} and len(resolution) < 3:
        raise HTTPException(status_code=422, detail={"code": "reason_required"})
    row.status = status
    row.resolution = resolution
    row.admin_id = user.id
    row.updated_at = utcnow()
    lot = db.get(Lot, row.lot_id)
    if lot and status == "resolved" and lot.status == "disputed":
        lot.status = "handed_over"
    audit(db, user, "dispute_resolve", "dispute", dispute_id, {"status": status}, request)
    notify(db, row.raised_by, "Dispute update", resolution or status, "dispute")
    if row.against_user:
        notify(db, row.against_user, "Dispute update", resolution or status, "dispute")
    db.commit()
    return {"id": row.id, "status": row.status}


@router.get("/audit")
def audit_log(user: User = Depends(admin), db: Session = Depends(get_db)):
    rows = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(300).all()
    return [
        {
            "id": row.id,
            "actor_id": row.actor_id,
            "action": row.action,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "detail": row.detail,
            "at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.get("/sync")
def sync_monitor(user: User = Depends(admin), db: Session = Depends(get_db)):
    rows = db.query(SyncQueueLog).order_by(SyncQueueLog.created_at.desc()).limit(200).all()
    return [
        {"id": row.id, "user_id": row.user_id, "key": row.idempotency_key, "entity": row.entity, "status": row.status, "error": row.error, "at": row.created_at.isoformat()}
        for row in rows
    ]


@router.get("/activity")
def activity(user: User = Depends(admin), db: Session = Depends(get_db)):
    from app.models import LotEvent

    events = []
    for row in db.query(LotEvent).order_by(LotEvent.created_at.desc()).limit(15).all():
        lot = db.get(Lot, row.lot_id)
        events.append({"kind": row.event_type, "at": row.created_at.isoformat(), "lot_id": lot.public_id if lot else "", "note": row.note})
    for row in db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(10).all():
        events.append({"kind": row.action, "at": row.created_at.isoformat(), "lot_id": "", "note": row.entity_type})
    events.sort(key=lambda item: item["at"], reverse=True)
    return events[:20]


@router.post("/reset-demo")
def reset_demo(request: Request, user: User = Depends(admin), db: Session = Depends(get_db)):
    from app.config import get_settings
    from app.services.demo import reset_demo_data

    if not get_settings().demo_mode:
        raise HTTPException(status_code=403, detail={"code": "demo_disabled"})
    result = reset_demo_data(db)
    audit(db, user, "demo_reset", "demo", user.id, result, request)
    db.commit()
    return result


@router.get("/analytics")
def analytics(user: User = Depends(admin), db: Session = Depends(get_db)):
    by_status = db.query(Lot.status, func.count(Lot.id)).group_by(Lot.status).all()
    by_mode = db.query(Transaction.mode, func.coalesce(func.sum(Transaction.paid_amount), 0)).group_by(Transaction.mode).all()
    return {
        "lots_by_status": {status: count for status, count in by_status},
        "paid_by_mode": {mode or "unset": round(float(total), 2) for mode, total in by_mode},
        "impact": impact(db),
        "disputes": db.query(Dispute).count(),
    }
