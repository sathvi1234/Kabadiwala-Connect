from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Dispute, DisputeEvidence, Lot, RatingFeedback, RecyclerProfile, User, utcnow
from app.security import get_current_user, require_roles
from app.services.common import notify
from app.services.reliability import reliability
from app.storage import save_upload

router = APIRouter(tags=["trust"])


@router.post("/api/ratings")
def rate(payload: dict, user: User = Depends(require_roles("collector")), db: Session = Depends(get_db)):
    lot = db.query(Lot).filter((Lot.id == payload.get("lot_id")) | (Lot.public_id == payload.get("lot_id"))).one_or_none()
    if not lot or lot.collector_id != user.id:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    if lot.status not in {"handed_over", "processing", "completed"}:
        raise HTTPException(status_code=409, detail={"code": "bad_status"})
    stars = int(payload.get("stars", 0))
    if stars < 1 or stars > 5:
        raise HTTPException(status_code=422, detail={"code": "bad_stars"})
    from app.models import Pickup

    pickup = db.query(Pickup).filter(Pickup.lot_id == lot.id, Pickup.status.in_(["accepted", "completed"])).order_by(Pickup.created_at.desc()).first()
    if not pickup:
        raise HTTPException(status_code=409, detail={"code": "pickup_not_accepted"})
    existing = db.query(RatingFeedback).filter(RatingFeedback.lot_id == lot.id, RatingFeedback.collector_id == user.id).one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail={"code": "already_rated"})
    row = RatingFeedback(
        lot_id=lot.id,
        collector_id=user.id,
        recycler_id=pickup.recycler_id,
        stars=stars,
        comment=str(payload.get("comment", ""))[:500],
        created_at=utcnow(),
    )
    db.add(row)
    ratings = db.query(RatingFeedback).filter(RatingFeedback.recycler_id == pickup.recycler_id).all()
    profile = db.query(RecyclerProfile).filter(RecyclerProfile.user_id == pickup.recycler_id).one()
    profile.rating_count = len(ratings) + 1
    profile.rating_avg = round((sum(r.stars for r in ratings) + stars) / profile.rating_count, 2)
    profile.reliability_score = reliability(db, pickup.recycler_id)["score"]
    db.commit()
    return {"stars": stars, "rating": profile.rating_avg}


@router.get("/api/ratings/me")
def my_ratings(user: User = Depends(require_roles("recycler")), db: Session = Depends(get_db)):
    rows = db.query(RatingFeedback).filter(RatingFeedback.recycler_id == user.id).order_by(RatingFeedback.created_at.desc()).all()
    return [{"stars": r.stars, "comment": r.comment, "at": r.created_at.isoformat()} for r in rows]


@router.post("/api/disputes")
async def raise_dispute(
    lot_id: str = Form(...),
    reason: str = Form(...),
    file: UploadFile | None = File(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role not in {"collector", "recycler"}:
        raise HTTPException(status_code=403, detail={"code": "forbidden"})
    if len(reason.strip()) < 8:
        raise HTTPException(status_code=422, detail={"code": "bad_reason"})
    lot = db.query(Lot).filter((Lot.id == lot_id) | (Lot.public_id == lot_id)).one_or_none()
    if not lot:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    from app.models import Pickup

    pickup = db.query(Pickup).filter(Pickup.lot_id == lot.id).order_by(Pickup.created_at.desc()).first()
    if user.role == "collector" and lot.collector_id != user.id:
        raise HTTPException(status_code=403, detail={"code": "forbidden"})
    if user.role == "recycler" and (not pickup or pickup.recycler_id != user.id):
        raise HTTPException(status_code=403, detail={"code": "forbidden"})
    against = pickup.recycler_id if user.role == "collector" and pickup else lot.collector_id
    dispute = Dispute(lot_id=lot.id, raised_by=user.id, against_user=against, reason=reason.strip(), status="open", created_at=utcnow(), updated_at=utcnow())
    db.add(dispute)
    db.flush()
    if file and file.filename:
        path = await save_upload(file, "evidence")
        db.add(DisputeEvidence(dispute_id=dispute.id, file_path=path, uploaded_by=user.id, created_at=utcnow()))
    lot.status = "disputed"
    notify(db, against, "Dispute opened", f"A dispute was opened on {lot.public_id}.", "dispute", {"lot": lot.public_id})
    db.commit()
    return {"id": dispute.id, "status": dispute.status}


@router.get("/api/disputes")
def list_disputes(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Dispute)
    if user.role != "admin":
        q = q.filter((Dispute.raised_by == user.id) | (Dispute.against_user == user.id))
    rows = q.order_by(Dispute.created_at.desc()).all()
    out = []
    for row in rows:
        lot = db.get(Lot, row.lot_id)
        evidence = db.query(DisputeEvidence).filter(DisputeEvidence.dispute_id == row.id).all()
        out.append(
            {
                "id": row.id,
                "lot_id": lot.public_id if lot else row.lot_id,
                "reason": row.reason,
                "status": row.status,
                "resolution": row.resolution,
                "created_at": row.created_at.isoformat(),
                "evidence": [{"path": e.file_path} for e in evidence] if user.role == "admin" or user.id == row.raised_by else [],
            }
        )
    return out
