from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Material, PriceFeed, User, utcnow
from app.security import deny_if_demo, get_current_user, require_roles
from app.services.alerts import evaluate_rules
from app.services.common import audit, material_by_code
from app.services.pricing import change_pct, history, latest_price

router = APIRouter(prefix="/api/prices", tags=["prices"])


@router.get("/materials")
def materials(db: Session = Depends(get_db)):
    rows = db.query(Material).order_by(Material.code.asc()).all()
    return [
        {
            "code": m.code,
            "name": {"en": m.name_en, "hi": m.name_hi, "mr": m.name_mr},
            "co2_factor": m.co2_factor,
            "factor_source": m.factor_source,
        }
        for m in rows
    ]


@router.get("/board")
def board(city: str = "", material: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    city = city or (user.collector_profile.city if user.collector_profile else "Hyderabad")
    mats = db.query(Material).order_by(Material.code.asc()).all()
    if material:
        mats = [m for m in mats if m.code == material]
    items = []
    for mat in mats:
        row = latest_price(db, mat, city)
        points = history(db, mat, city, 30)
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


@router.get("/history")
def price_history(material: str, city: str = "", range: str = "30d", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    days = {"7d": 7, "30d": 30, "90d": 90, "1y": 365}.get(range)
    if not days:
        raise HTTPException(status_code=422, detail={"code": "bad_range"})
    mat = material_by_code(db, material)
    points = history(db, mat, city, days)
    return {"material": material, "city": city, "range": range, "change_pct": change_pct(points), "points": points}


class PriceIn(BaseModel):
    material_code: str
    price_per_kg: float = Field(gt=0, lt=100000)
    source: str = Field(min_length=2, max_length=120)
    market: str = Field(min_length=2, max_length=100)
    recorded_on: str


@router.get("/admin")
def admin_list(user: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    rows = db.query(PriceFeed).order_by(PriceFeed.recorded_on.desc()).limit(400).all()
    out = []
    for row in rows:
        mat = db.get(Material, row.material_id)
        out.append(
            {
                "id": row.id,
                "material": mat.code if mat else "",
                "price_per_kg": row.price_per_kg,
                "source": row.source,
                "market": row.market,
                "recorded_on": row.recorded_on.isoformat(),
            }
        )
    return out


@router.post("/admin")
def admin_create(payload: PriceIn, request: Request, user: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    mat = material_by_code(db, payload.material_code)
    row = PriceFeed(
        material_id=mat.id,
        price_per_kg=payload.price_per_kg,
        source=payload.source.strip(),
        market=payload.market.strip(),
        recorded_on=date.fromisoformat(payload.recorded_on),
        created_by=user.id,
        created_at=utcnow(),
    )
    db.add(row)
    audit(db, user, "price_create", "price_feed", payload.material_code, payload.model_dump(), request)
    evaluate_rules(db)
    db.commit()
    return {"id": row.id}


@router.put("/admin/{price_id}")
def admin_update(price_id: str, payload: PriceIn, request: Request, user: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    row = db.get(PriceFeed, price_id)
    if not row:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    mat = material_by_code(db, payload.material_code)
    row.material_id = mat.id
    row.price_per_kg = payload.price_per_kg
    row.source = payload.source.strip()
    row.market = payload.market.strip()
    row.recorded_on = date.fromisoformat(payload.recorded_on)
    audit(db, user, "price_update", "price_feed", price_id, payload.model_dump(), request)
    evaluate_rules(db)
    db.commit()
    return {"id": row.id}


@router.delete("/admin/{price_id}")
def admin_delete(price_id: str, request: Request, user: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    deny_if_demo(user)
    row = db.get(PriceFeed, price_id)
    if not row:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    audit(db, user, "price_delete", "price_feed", price_id, {}, request)
    db.delete(row)
    db.commit()
    return {"deleted": True}
