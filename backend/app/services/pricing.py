from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models import Material, PriceFeed
from app.services.common import money


def latest_price(db: Session, material: Material, city: str) -> PriceFeed | None:
    row = (
        db.query(PriceFeed)
        .filter(PriceFeed.material_id == material.id, PriceFeed.market == city)
        .order_by(PriceFeed.recorded_on.desc(), PriceFeed.created_at.desc())
        .first()
    )
    if row:
        return row
    return (
        db.query(PriceFeed)
        .filter(PriceFeed.material_id == material.id)
        .order_by(PriceFeed.recorded_on.desc(), PriceFeed.created_at.desc())
        .first()
    )


def estimate_value(db: Session, material: Material, weight_kg: float, city: str) -> dict:
    row = latest_price(db, material, city)
    if not row:
        return {
            "price_per_kg": 0,
            "value": 0,
            "source": "",
            "date": "",
            "market": city,
            "low": 0,
            "high": 0,
            "confidence": 0,
        }
    value = money(weight_kg * row.price_per_kg)
    age = (date.today() - row.recorded_on).days if isinstance(row.recorded_on, date) else 0
    confidence = 0.9 if age <= 3 else 0.75 if age <= 14 else 0.55
    return {
        "price_per_kg": row.price_per_kg,
        "value": value,
        "source": row.source,
        "date": row.recorded_on.isoformat(),
        "market": row.market,
        "low": money(value * 0.9),
        "high": money(value * 1.1),
        "confidence": confidence,
    }


def history(db: Session, material: Material, city: str, days: int) -> list[dict]:
    start = date.today() - timedelta(days=days)
    q = db.query(PriceFeed).filter(PriceFeed.material_id == material.id, PriceFeed.recorded_on >= start)
    if city:
        scoped = q.filter(PriceFeed.market == city)
        rows = scoped.order_by(PriceFeed.recorded_on.asc()).all()
        if not rows:
            rows = q.order_by(PriceFeed.recorded_on.asc()).all()
    else:
        rows = q.order_by(PriceFeed.recorded_on.asc()).all()
    return [
        {"date": r.recorded_on.isoformat(), "price": r.price_per_kg, "source": r.source, "market": r.market}
        for r in rows
    ]


def change_pct(points: list[dict]) -> float:
    if len(points) < 2 or not points[0]["price"]:
        return 0.0
    return round((points[-1]["price"] - points[0]["price"]) / points[0]["price"] * 100, 2)
