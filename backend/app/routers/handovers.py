from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Handover, Lot, LotEvent, Pickup, User, utcnow
from app.security import require_roles
from app.services.common import parse_dt
from app.services.payments import finalize_handover
from app.services.verification import handover_flags
from app.routers.lots import _load, attach_photo

router = APIRouter(prefix="/api/handovers", tags=["handovers"])


def _pickup_for(db: Session, lot: Lot, recycler_id: str | None = None) -> Pickup:
    q = db.query(Pickup).filter(Pickup.lot_id == lot.id, Pickup.status == "accepted")
    if recycler_id:
        q = q.filter(Pickup.recycler_id == recycler_id)
    pickup = q.order_by(Pickup.created_at.desc()).first()
    if not pickup:
        raise HTTPException(status_code=409, detail={"code": "pickup_not_accepted"})
    return pickup


@router.post("/{lot_id}/collector")
async def collector_confirm(
    lot_id: str,
    lat: float = Form(...),
    lng: float = Form(...),
    captured_at: str = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(require_roles("collector")),
    db: Session = Depends(get_db),
):
    lot = _load(db, lot_id)
    if lot.collector_id != user.id:
        raise HTTPException(status_code=403, detail={"code": "forbidden"})
    pickup = _pickup_for(db, lot)
    when = parse_dt(captured_at)
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=422, detail={"code": "empty_file"})
    handover = db.query(Handover).filter(Handover.lot_id == lot.id).one_or_none()
    if not handover:
        handover = Handover(lot_id=lot.id, created_at=utcnow())
        db.add(handover)
        db.flush()
    photo = attach_photo(db, lot, raw, "handover")
    handover.lat = lat
    handover.lng = lng
    handover.photo_path = photo.path
    handover.collector_confirmed_at = when
    handover.flags = handover_flags(lot.lat, lot.lng, lat, lng, when, True, lot.weight_kg, handover.weight_verified_kg)
    lot.flags = {**(lot.flags or {}), **handover.flags}
    db.add(LotEvent(lot_id=lot.id, event_type="collector_confirm", actor_id=user.id, actor_role="collector", lat=lat, lng=lng, created_at=utcnow()))
    finalize_handover(db, lot, handover, pickup.recycler_id)
    db.commit()
    return {"lot_id": lot.public_id, "status": lot.status, "flags": handover.flags}


@router.post("/{lot_id}/recycler")
async def recycler_confirm(
    lot_id: str,
    weight_kg: float = Form(...),
    lat: float = Form(...),
    lng: float = Form(...),
    captured_at: str = Form(...),
    file: UploadFile | None = File(None),
    user: User = Depends(require_roles("recycler")),
    db: Session = Depends(get_db),
):
    if weight_kg <= 0 or weight_kg > 20000:
        raise HTTPException(status_code=422, detail={"code": "bad_weight"})
    lot = _load(db, lot_id)
    pickup = _pickup_for(db, lot, user.id)
    when = parse_dt(captured_at)
    handover = db.query(Handover).filter(Handover.lot_id == lot.id).one_or_none()
    if not handover:
        handover = Handover(lot_id=lot.id, created_at=utcnow())
        db.add(handover)
        db.flush()
    has_photo = bool(handover.photo_path)
    if file is not None:
        raw = await file.read()
        if raw:
            photo = attach_photo(db, lot, raw, "handover")
            handover.photo_path = photo.path
            has_photo = True
    handover.weight_verified_kg = weight_kg
    handover.weight_difference_kg = round(weight_kg - lot.weight_kg, 3)
    handover.lat = lat
    handover.lng = lng
    handover.recycler_confirmed_at = when
    handover.flags = handover_flags(lot.lat, lot.lng, lat, lng, when, has_photo, lot.weight_kg, weight_kg)
    lot.flags = {**(lot.flags or {}), **handover.flags}
    db.add(
        LotEvent(
            lot_id=lot.id,
            event_type="recycler_confirm",
            actor_id=user.id,
            actor_role="recycler",
            note=f"weight {weight_kg}",
            lat=lat,
            lng=lng,
            created_at=utcnow(),
        )
    )
    tx = finalize_handover(db, lot, handover, pickup.recycler_id)
    db.commit()
    return {"lot_id": lot.public_id, "status": lot.status, "flags": handover.flags, "transaction_id": tx.public_id if tx else None}


@router.post("/{lot_id}/processing")
def processing(lot_id: str, user: User = Depends(require_roles("recycler")), db: Session = Depends(get_db)):
    lot = _load(db, lot_id)
    pickup = _pickup_for(db, lot, user.id)
    if lot.status not in {"handed_over", "processing"}:
        raise HTTPException(status_code=409, detail={"code": "bad_status"})
    lot.status = "completed"
    pickup.status = "completed"
    db.add(LotEvent(lot_id=lot.id, event_type="processing", actor_id=user.id, actor_role="recycler", note="Processing complete", created_at=utcnow()))
    db.commit()
    return {"lot_id": lot.public_id, "status": lot.status}
