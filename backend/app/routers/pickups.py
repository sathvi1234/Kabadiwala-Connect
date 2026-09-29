from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Lot, LotEvent, Pickup, RecyclerProfile, User, utcnow
from app.security import get_current_user, require_roles
from app.services.common import parse_dt

router = APIRouter(prefix="/api/pickups", tags=["pickups"])


class PickupIn(BaseModel):
    lot_id: str
    recycler_id: str
    scheduled_at: str
    note: str = ""


def _lot(db: Session, lot_id: str) -> Lot:
    lot = db.query(Lot).filter((Lot.id == lot_id) | (Lot.public_id == lot_id)).one_or_none()
    if not lot:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    return lot


@router.post("")
def schedule(payload: PickupIn, user: User = Depends(require_roles("collector")), db: Session = Depends(get_db)):
    lot = _lot(db, payload.lot_id)
    if lot.collector_id != user.id:
        raise HTTPException(status_code=403, detail={"code": "forbidden"})
    if lot.status not in {"open", "pickup_scheduled"}:
        raise HTTPException(status_code=409, detail={"code": "bad_status"})
    profile = db.query(RecyclerProfile).filter(RecyclerProfile.user_id == payload.recycler_id, RecyclerProfile.status == "approved").one_or_none()
    if not profile:
        raise HTTPException(status_code=422, detail={"code": "recycler_pending"})
    when = parse_dt(payload.scheduled_at)
    pickup = Pickup(
        lot_id=lot.id,
        recycler_id=payload.recycler_id,
        collector_id=user.id,
        scheduled_at=when,
        status="requested",
        note=payload.note[:300],
        created_at=utcnow(),
    )
    db.add(pickup)
    lot.status = "pickup_scheduled"
    db.add(
        LotEvent(
            lot_id=lot.id,
            event_type="pickup_scheduled",
            actor_id=user.id,
            actor_role="collector",
            note=profile.business_name,
            created_at=utcnow(),
            meta={"scheduled_at": when.isoformat()},
        )
    )
    db.commit()
    return {"id": pickup.id, "status": pickup.status, "lot_id": lot.public_id}


class PickupPatch(BaseModel):
    status: str


@router.patch("/{pickup_id}")
def update_pickup(pickup_id: str, payload: PickupPatch, user: User = Depends(require_roles("recycler")), db: Session = Depends(get_db)):
    pickup = db.get(Pickup, pickup_id)
    if not pickup or pickup.recycler_id != user.id:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    if payload.status not in {"accepted", "rejected"}:
        raise HTTPException(status_code=422, detail={"code": "bad_status"})
    if user.recycler_profile.status != "approved":
        raise HTTPException(status_code=403, detail={"code": "recycler_pending"})
    pickup.status = payload.status
    lot = db.get(Lot, pickup.lot_id)
    if payload.status == "rejected":
        lot.status = "open"
    db.add(
        LotEvent(
            lot_id=lot.id,
            event_type="pickup_accepted" if payload.status == "accepted" else "pickup_rejected",
            actor_id=user.id,
            actor_role="recycler",
            note=payload.status,
            created_at=utcnow(),
        )
    )
    db.commit()
    return {"id": pickup.id, "status": pickup.status}


@router.get("")
def list_pickups(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Pickup)
    if user.role == "collector":
        q = q.filter(Pickup.collector_id == user.id)
    elif user.role == "recycler":
        q = q.filter(Pickup.recycler_id == user.id)
    rows = q.order_by(Pickup.scheduled_at.desc()).limit(200).all()
    out = []
    for pickup in rows:
        lot = db.get(Lot, pickup.lot_id)
        recycler = db.get(User, pickup.recycler_id)
        profile = recycler.recycler_profile if recycler else None
        out.append(
            {
                "id": pickup.id,
                "lot_id": lot.public_id if lot else pickup.lot_id,
                "lot_status": lot.status if lot else "",
                "material": lot.material.code if lot and lot.material else "",
                "weight_kg": lot.weight_kg if lot else 0,
                "recycler_id": pickup.recycler_id,
                "recycler_name": profile.business_name if profile else "",
                "availability": profile.availability if profile else "",
                "scheduled_at": pickup.scheduled_at.isoformat(),
                "status": pickup.status,
                "note": pickup.note,
                "lat": lot.lat if lot else None,
                "lng": lot.lng if lot else None,
            }
        )
    return out
