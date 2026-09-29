from sqlalchemy.orm import Session

from app.models import Alert, Material, Notification, PriceAlertRule, PriceFeed, utcnow
from app.services.common import notify


def ensure_auto_rules(db: Session, collector_id: str, material_codes: list[str], city: str):
    materials = db.query(Material).filter(Material.code.in_(material_codes or [])).all()
    for material in materials:
        exists = (
            db.query(PriceAlertRule)
            .filter(PriceAlertRule.collector_id == collector_id, PriceAlertRule.material_id == material.id, PriceAlertRule.auto.is_(True))
            .first()
        )
        if exists:
            continue
        db.add(
            PriceAlertRule(
                collector_id=collector_id,
                material_id=material.id,
                city=city,
                direction="change",
                change_pct=5,
                auto=True,
                active=True,
            )
        )


def evaluate_rules(db: Session):
    rules = db.query(PriceAlertRule).filter(PriceAlertRule.active.is_(True)).all()
    fired = 0
    for rule in rules:
        q = db.query(PriceFeed).filter(PriceFeed.material_id == rule.material_id)
        if rule.city:
            scoped = q.filter(PriceFeed.market == rule.city)
            rows = scoped.order_by(PriceFeed.recorded_on.desc(), PriceFeed.created_at.desc()).limit(2).all()
            if not rows:
                rows = q.order_by(PriceFeed.recorded_on.desc(), PriceFeed.created_at.desc()).limit(2).all()
        else:
            rows = q.order_by(PriceFeed.recorded_on.desc(), PriceFeed.created_at.desc()).limit(2).all()
        if not rows or rows[0].id == rule.last_price_id:
            continue
        latest = rows[0]
        previous = rows[1] if len(rows) > 1 else None
        hit = False
        if rule.direction == "above" and rule.threshold is not None and latest.price_per_kg >= rule.threshold:
            hit = True
        elif rule.direction == "below" and rule.threshold is not None and latest.price_per_kg <= rule.threshold:
            hit = True
        elif rule.direction == "change" and previous and previous.price_per_kg:
            pct = abs(latest.price_per_kg - previous.price_per_kg) / previous.price_per_kg * 100
            hit = pct >= (rule.change_pct or 5)
        if not hit:
            continue
        material = db.get(Material, rule.material_id)
        message = f"{material.code if material else 'Material'} is ₹{latest.price_per_kg:.2f}/kg in {latest.market} ({latest.recorded_on.isoformat()})."
        db.add(Alert(user_id=rule.collector_id, rule_id=rule.id, message=message, created_at=utcnow()))
        notify(db, rule.collector_id, "Price alert", message, "price", {"material": material.code if material else "", "price": latest.price_per_kg})
        rule.last_price_id = latest.id
        fired += 1
    return fired


def unread_count(db: Session, user_id: str) -> int:
    return db.query(Notification).filter(Notification.user_id == user_id, Notification.read.is_(False)).count()
