from datetime import timedelta

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Lot, Transaction, User, utcnow
from app.security import require_roles
from app.services.common import material_by_code
from app.services.impact import impact
from app.services.rewards import current_balance, verified_handover_count
from app.storage import save_upload

router = APIRouter(prefix="/api/collectors", tags=["collectors"])


@router.get("/me/stats")
def stats(user: User = Depends(require_roles("collector")), db: Session = Depends(get_db)):
    lots = db.query(Lot).filter(Lot.collector_id == user.id).all()
    paid = db.query(func.coalesce(func.sum(Transaction.paid_amount), 0)).filter(Transaction.collector_id == user.id).scalar() or 0
    pending = (
        db.query(func.coalesce(func.sum(Transaction.amount - Transaction.paid_amount), 0))
        .filter(Transaction.collector_id == user.id, Transaction.status != "paid")
        .scalar()
        or 0
    )
    by_status = {}
    for lot in lots:
        by_status[lot.status] = by_status.get(lot.status, 0) + 1
    from app.models import PaymentLine

    this_key = utcnow().strftime("%Y-%m")
    previous = (utcnow().replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    month_totals = {"this": 0.0, "last": 0.0}
    lines = (
        db.query(PaymentLine)
        .join(Transaction, Transaction.id == PaymentLine.transaction_id)
        .filter(Transaction.collector_id == user.id)
        .all()
    )
    for line in lines:
        key = line.created_at.strftime("%Y-%m")
        if key == this_key:
            month_totals["this"] += line.amount
        elif key == previous:
            month_totals["last"] += line.amount
    return {
        "lots": len(lots),
        "verified_handovers": verified_handover_count(db, user.id),
        "earned": round(float(paid), 2),
        "pending": round(float(pending), 2),
        "balance": current_balance(db, user.id),
        "by_status": by_status,
        "this_month": round(month_totals["this"], 2),
        "last_month": round(month_totals["last"], 2),
        "impact": impact(db, collector_id=user.id),
    }


@router.get("/me/earnings")
def earnings(bucket: str = "month", user: User = Depends(require_roles("collector")), db: Session = Depends(get_db)):
    from app.models import Material, PaymentLine

    lines = (
        db.query(PaymentLine, Transaction, Lot, Material)
        .join(Transaction, Transaction.id == PaymentLine.transaction_id)
        .join(Lot, Lot.id == Transaction.lot_id)
        .join(Material, Material.id == Lot.material_id)
        .filter(Transaction.collector_id == user.id)
        .order_by(PaymentLine.created_at.asc())
        .all()
    )
    series: dict[str, float] = {}
    by_material: dict[str, float] = {}
    for pay, _tx, _lot, material in lines:
        if bucket == "day":
            key = pay.created_at.strftime("%Y-%m-%d")
        elif bucket == "week":
            key = pay.created_at.strftime("%Y-W%W")
        else:
            key = pay.created_at.strftime("%Y-%m")
        series[key] = round(series.get(key, 0) + pay.amount, 2)
        by_material[material.code] = round(by_material.get(material.code, 0) + pay.amount, 2)
    return {
        "bucket": bucket,
        "series": [{"period": k, "amount": v} for k, v in series.items()],
        "by_material": [{"material": k, "amount": v} for k, v in by_material.items()],
    }


@router.patch("/me")
def update_profile(payload: dict, user: User = Depends(require_roles("collector")), db: Session = Depends(get_db)):
    profile = user.collector_profile
    if not profile:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    for field in ("area", "city", "emergency_contact"):
        if field in payload:
            setattr(profile, field, str(payload[field])[:200])
    if "lat" in payload:
        profile.lat = payload["lat"]
    if "lng" in payload:
        profile.lng = payload["lng"]
    if "materials" in payload and isinstance(payload["materials"], list):
        for code in payload["materials"]:
            material_by_code(db, code)
        profile.materials = payload["materials"]
    if "low_data_mode" in payload:
        profile.low_data_mode = bool(payload["low_data_mode"])
    if "voice_nav_enabled" in payload:
        profile.voice_nav_enabled = bool(payload["voice_nav_enabled"])
    if "image_quality" in payload:
        quality = float(payload["image_quality"])
        if not 0.3 <= quality <= 0.95:
            raise HTTPException(status_code=422, detail={"code": "bad_quality"})
        profile.image_quality = quality
    db.commit()
    from app.routers.auth import _public_user

    return _public_user(user, db)


@router.post("/me/photo")
async def photo(file: UploadFile = File(...), user: User = Depends(require_roles("collector")), db: Session = Depends(get_db)):
    path = await save_upload(file, "photos", images_only=True, recompress=True)
    user.collector_profile.profile_photo_path = path
    user.collector_profile.user = user
    db.commit()
    return {"path": path}


@router.get("")
def directory(q: str = "", user: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    rows = db.query(User).filter(User.role == "collector").order_by(User.created_at.desc()).all()
    result = []
    for row in rows:
        if q and q.lower() not in row.name.lower() and q not in row.phone:
            continue
        profile = row.collector_profile
        lots = db.query(Lot).filter(Lot.collector_id == row.id).count()
        earned = db.query(func.coalesce(func.sum(Transaction.paid_amount), 0)).filter(Transaction.collector_id == row.id).scalar() or 0
        result.append(
            {
                "id": row.id,
                "name": row.name,
                "phone": row.phone,
                "language": row.preferred_language,
                "area": profile.area if profile else "",
                "city": profile.city if profile else "",
                "lots": lots,
                "earnings": round(float(earned), 2),
                "active": row.is_active,
            }
        )
    return result
