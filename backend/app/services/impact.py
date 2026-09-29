from sqlalchemy.orm import Session

from app.models import Lot, Material


def impact(db: Session, collector_id: str | None = None, recycler_id: str | None = None) -> dict:
    q = db.query(Lot, Material).join(Material, Material.id == Lot.material_id).filter(Lot.status.in_(["handed_over", "processing", "completed"]))
    if collector_id:
        q = q.filter(Lot.collector_id == collector_id)
    rows = q.all()
    if recycler_id:
        from app.models import Pickup

        lot_ids = {p.lot_id for p in db.query(Pickup).filter(Pickup.recycler_id == recycler_id, Pickup.status.in_(["accepted", "completed"])).all()}
        rows = [pair for pair in rows if pair[0].id in lot_ids]
    by_material = {}
    weight = 0.0
    co2 = 0.0
    for lot, material in rows:
        weight += lot.weight_kg
        saved = lot.weight_kg * (material.co2_factor or 0)
        co2 += saved
        bucket = by_material.setdefault(material.code, {"weight_kg": 0, "co2_kg": 0, "source": material.factor_source})
        bucket["weight_kg"] = round(bucket["weight_kg"] + lot.weight_kg, 2)
        bucket["co2_kg"] = round(bucket["co2_kg"] + saved, 2)
    return {"weight_kg": round(weight, 2), "co2_kg": round(co2, 2), "lots": len(rows), "by_material": by_material}
