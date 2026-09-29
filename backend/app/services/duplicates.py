from datetime import timedelta

from sqlalchemy.orm import Session

from app.models import Lot, LotPhoto
from app.services.common import haversine_km
from app.services.images import similarity


def find_duplicate(db: Session, lot: Lot, phash: str) -> dict | None:
    if not phash:
        return None
    since = lot.captured_at - timedelta(hours=48)
    others = (
        db.query(Lot)
        .filter(Lot.id != lot.id, Lot.collector_id == lot.collector_id, Lot.captured_at >= since, Lot.material_id == lot.material_id)
        .all()
    )
    best = None
    for other in others:
        if other.weight_kg and abs(other.weight_kg - lot.weight_kg) / max(other.weight_kg, 0.01) > 0.15:
            continue
        close_space = False
        if None not in (lot.lat, lot.lng, other.lat, other.lng):
            close_space = haversine_km(lot.lat, lot.lng, other.lat, other.lng) <= 1
        close_time = abs((lot.captured_at - other.captured_at).total_seconds()) <= 6 * 3600
        if not (close_space or close_time):
            continue
        photos = db.query(LotPhoto).filter(LotPhoto.lot_id == other.id).all()
        score = max((similarity(phash, p.phash) for p in photos if p.phash), default=0)
        if score >= 0.85 and (best is None or score > best["score"]):
            best = {"lot_id": other.public_id, "score": score}
    return best
