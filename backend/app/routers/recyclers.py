from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Material, RecyclerDocument, RecyclerOffer, RecyclerProfile, User, utcnow
from app.realtime import bump
from app.security import get_current_user, require_roles
from app.services.common import material_by_code
from app.services.matching import candidates
from app.services.reliability import reliability
from app.storage import save_upload

router = APIRouter(prefix="/api/recyclers", tags=["recyclers"])


def _approved(user: User) -> RecyclerProfile:
    profile = user.recycler_profile
    if not profile:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    if profile.status != "approved":
        raise HTTPException(status_code=403, detail={"code": "recycler_pending"})
    return profile


@router.get("/nearby")
def nearby(
    lat: float,
    lng: float,
    material: str,
    weight: float = 1,
    max_km: float | None = None,
    availability: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mat = material_by_code(db, material)
    return candidates(db, lat, lng, mat, weight, max_km, availability)


@router.get("/me")
def me(user: User = Depends(require_roles("recycler")), db: Session = Depends(get_db)):
    profile = user.recycler_profile
    docs = db.query(RecyclerDocument).filter(RecyclerDocument.recycler_id == user.id).all()
    offers = (
        db.query(RecyclerOffer)
        .filter(RecyclerOffer.recycler_id == user.id, RecyclerOffer.lot_id.is_(None), RecyclerOffer.active.is_(True))
        .all()
    )
    return {
        "status": profile.status,
        "business_name": profile.business_name,
        "availability": profile.availability,
        "rating": profile.rating_avg,
        "reliability": reliability(db, user.id),
        "documents": [{"id": d.id, "type": d.doc_type, "path": d.file_path} for d in docs],
        "offers": [
            {
                "id": o.id,
                "material_id": o.material_id,
                "material": db.get(Material, o.material_id).code if db.get(Material, o.material_id) else "",
                "price_per_kg": o.price_per_kg,
            }
            for o in offers
        ],
    }


class AvailabilityIn(BaseModel):
    status: str
    next_slot: str | None = None


@router.patch("/me/availability")
def set_availability(payload: AvailabilityIn, user: User = Depends(require_roles("recycler")), db: Session = Depends(get_db)):
    profile = _approved(user)
    if payload.status not in {"available", "busy", "offline"}:
        raise HTTPException(status_code=422, detail={"code": "bad_status"})
    profile.availability = payload.status
    profile.next_slot = payload.next_slot
    db.commit()
    bump()
    return {"availability": profile.availability, "next_slot": profile.next_slot}


class OfferIn(BaseModel):
    material_code: str
    price_per_kg: float = Field(gt=0, lt=100000)


@router.put("/me/offers")
def set_offer(payload: OfferIn, user: User = Depends(require_roles("recycler")), db: Session = Depends(get_db)):
    _approved(user)
    mat = material_by_code(db, payload.material_code)
    if mat.code not in (user.recycler_profile.materials or []):
        raise HTTPException(status_code=422, detail={"code": "material_not_accepted"})
    current = (
        db.query(RecyclerOffer)
        .filter(RecyclerOffer.recycler_id == user.id, RecyclerOffer.material_id == mat.id, RecyclerOffer.lot_id.is_(None))
        .all()
    )
    for row in current:
        row.active = False
    db.add(RecyclerOffer(recycler_id=user.id, material_id=mat.id, price_per_kg=payload.price_per_kg, active=True, created_at=utcnow()))
    db.commit()
    return {"material": mat.code, "price_per_kg": payload.price_per_kg}


@router.post("/me/documents")
async def add_doc(file: UploadFile = File(...), user: User = Depends(require_roles("recycler")), db: Session = Depends(get_db)):
    path = await save_upload(file, "documents")
    db.add(RecyclerDocument(recycler_id=user.id, doc_type="licence", file_path=path, created_at=utcnow()))
    db.commit()
    return {"path": path}


@router.get("/{recycler_id}/history")
def history(recycler_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.models import Dispute, Handover, Lot, Pickup

    profile = db.query(RecyclerProfile).filter(RecyclerProfile.user_id == recycler_id).one_or_none()
    if not profile or profile.status != "approved":
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    pickups = db.query(Pickup).filter(Pickup.recycler_id == recycler_id).order_by(Pickup.created_at.desc()).limit(50).all()
    items = []
    for pickup in pickups:
        lot = db.get(Lot, pickup.lot_id)
        handover = db.query(Handover).filter(Handover.lot_id == pickup.lot_id).one_or_none()
        items.append(
            {
                "lot_id": lot.public_id if lot else pickup.lot_id,
                "pickup_status": pickup.status,
                "scheduled_at": pickup.scheduled_at.isoformat(),
                "handover": bool(handover and handover.recycler_confirmed_at),
                "lot_status": lot.status if lot else "",
            }
        )
    disputes = db.query(Dispute).filter(Dispute.against_user == recycler_id).count()
    return {"business_name": profile.business_name, "verified": True, "reliability": reliability(db, recycler_id), "disputes": disputes, "history": items}
