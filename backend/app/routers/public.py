from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CommunityEvent, Lot, LotEvent, Material, RecyclerProfile, Testimonial, Transaction, User
from app.services.common import material_by_code
from app.services.impact import impact
from app.services.matching import candidates
from app.services.pricing import change_pct, estimate_value, history, latest_price

router = APIRouter(prefix="/api/public", tags=["public"])


@router.get("/verify/{lot_id}")
def verify(lot_id: str, db: Session = Depends(get_db)):
    lot = db.query(Lot).filter(Lot.public_id == lot_id).one_or_none()
    if not lot:
        return {"found": False}
    material = db.get(Material, lot.material_id)
    events = db.query(LotEvent).filter(LotEvent.lot_id == lot.id).order_by(LotEvent.created_at.asc()).all()
    flags = lot.flags or {}
    return {
        "found": True,
        "lot_id": lot.public_id,
        "status": lot.status,
        "material": material.code if material else "",
        "weight_kg": lot.weight_kg,
        "city": lot.city,
        "created_at": lot.created_at.isoformat(),
        "verification": {
            "gps": bool(flags.get("gps_present")),
            "photo": bool(flags.get("photo_present")),
            "time": bool(flags.get("time_ok")),
            "distance_flag": bool(flags.get("distance_suspicious")),
        },
        "timeline": [{"event": e.event_type, "at": e.created_at.isoformat()} for e in events],
    }


@router.get("/map")
def community_map(db: Session = Depends(get_db)):
    recyclers = db.query(RecyclerProfile).filter(RecyclerProfile.status == "approved").all()
    events = db.query(CommunityEvent).order_by(CommunityEvent.starts_at.asc()).all()
    areas = (
        db.query(Lot.city, func.sum(Lot.weight_kg), func.count(Lot.id))
        .filter(Lot.status.in_(["handed_over", "processing", "completed"]))
        .group_by(Lot.city)
        .all()
    )
    return {
        "recyclers": [
            {
                "business_name": r.business_name,
                "city": r.city,
                "lat": r.lat,
                "lng": r.lng,
                "materials": r.materials,
                "availability": r.availability,
                "verified": True,
            }
            for r in recyclers
        ],
        "events": [
            {"title": e.title, "city": e.city, "lat": e.lat, "lng": e.lng, "starts_at": e.starts_at.isoformat(), "description": e.description}
            for e in events
        ],
        "areas": [{"city": city, "weight_kg": round(float(weight or 0), 2), "lots": count} for city, weight, count in areas],
    }


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    diverted = impact(db)
    earned = db.query(func.coalesce(func.sum(Transaction.paid_amount), 0)).scalar() or 0
    return {
        "collectors": db.query(User).filter(User.role == "collector", User.is_active.is_(True)).count(),
        "recyclers": db.query(RecyclerProfile).filter(RecyclerProfile.status == "approved").count(),
        "lots": db.query(Lot).count(),
        "tonnes_diverted": round(diverted["weight_kg"] / 1000, 3),
        "weight_kg": diverted["weight_kg"],
        "co2_kg": diverted["co2_kg"],
        "earnings": round(float(earned), 2),
    }


@router.get("/prices")
def prices(city: str = "Hyderabad", db: Session = Depends(get_db)):
    items = []
    for mat in db.query(Material).order_by(Material.code.asc()).all():
        row = latest_price(db, mat, city)
        points = history(db, mat, city, 7)
        items.append(
            {
                "material": mat.code,
                "name": {"en": mat.name_en, "hi": mat.name_hi, "mr": mat.name_mr},
                "price_per_kg": row.price_per_kg if row else None,
                "source": row.source if row else "",
                "date": row.recorded_on.isoformat() if row else "",
                "market": row.market if row else city,
                "change_pct": change_pct(points),
            }
        )
    return {"city": city, "items": items}


@router.get("/prices/history")
def price_history(material: str, city: str = "Hyderabad", range: str = "30d", db: Session = Depends(get_db)):
    days = {"7d": 7, "30d": 30, "90d": 90, "1y": 365}.get(range)
    if not days:
        raise HTTPException(status_code=422, detail={"code": "bad_range"})
    mat = material_by_code(db, material)
    points = history(db, mat, city, days)
    step = max(1, len(points) // 24)
    spark = points[::step][-24:]
    return {"material": material, "city": city, "range": range, "change_pct": change_pct(points), "points": spark}


@router.get("/recommend")
def recommend(material: str = "PCB", weight: float = 1, lat: float = 17.44, lng: float = 78.49, db: Session = Depends(get_db)):
    mat = material_by_code(db, material)
    rows = candidates(db, lat, lng, mat, weight, 50, None)
    return {"ranked": rows[:5]}


@router.get("/activity")
def activity(db: Session = Depends(get_db)):
    events = db.query(LotEvent).order_by(LotEvent.created_at.desc()).limit(8).all()
    out = []
    for event in events:
        lot = db.get(Lot, event.lot_id)
        material = lot.material.code if lot and lot.material else ""
        out.append(
            {
                "event": event.event_type,
                "at": event.created_at.isoformat(),
                "material": material,
                "weight_kg": lot.weight_kg if lot else None,
                "city": lot.city if lot else "",
                "lot_id": lot.public_id if lot else "",
            }
        )
    return out


@router.get("/testimonials")
def testimonials(db: Session = Depends(get_db)):
    rows = db.query(Testimonial).order_by(Testimonial.created_at.asc()).all()
    return [
        {"name": row.name, "role": row.role, "city": row.city, "quote": {"en": row.quote_en, "hi": row.quote_hi, "mr": row.quote_mr}}
        for row in rows
    ]
