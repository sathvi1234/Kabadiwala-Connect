from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Lot, Material, RecyclerOffer, RecyclerProfile, User
from app.services.common import haversine_km, money


def standing_price(db: Session, recycler_id: str, material_id: str) -> float | None:
    offer = (
        db.query(RecyclerOffer)
        .filter(
            RecyclerOffer.recycler_id == recycler_id,
            RecyclerOffer.material_id == material_id,
            RecyclerOffer.lot_id.is_(None),
            RecyclerOffer.active.is_(True),
        )
        .order_by(RecyclerOffer.created_at.desc())
        .first()
    )
    return offer.price_per_kg if offer else None


def lot_offer(db: Session, recycler_id: str, lot_id: str) -> float | None:
    offer = (
        db.query(RecyclerOffer)
        .filter(RecyclerOffer.recycler_id == recycler_id, RecyclerOffer.lot_id == lot_id, RecyclerOffer.active.is_(True))
        .order_by(RecyclerOffer.created_at.desc())
        .first()
    )
    return offer.price_per_kg if offer else None


def candidates(db: Session, lat: float, lng: float, material: Material, weight: float, max_km: float | None, availability: str | None):
    settings = get_settings()
    rows = db.query(RecyclerProfile, User).join(User, User.id == RecyclerProfile.user_id).filter(RecyclerProfile.status == "approved", User.is_active.is_(True)).all()
    found = []
    for profile, user in rows:
        if material.code not in (profile.materials or []):
            continue
        if availability and profile.availability != availability:
            continue
        distance = haversine_km(lat, lng, profile.lat, profile.lng)
        if max_km is not None and distance > max_km:
            continue
        price = standing_price(db, user.id, material.id)
        found.append((profile, user, distance, price))
    prices = [p for *_, p in found if p]
    max_price = max(prices) if prices else 1
    ranked = []
    for profile, user, distance, price in found:
        dist_score = max(0.0, 1 - distance / 50)
        price_score = (price / max_price) if price else 0
        auth_score = 1.0
        avail_score = {"available": 1.0, "busy": 0.5, "offline": 0.0}.get(profile.availability, 0)
        rating_score = (profile.rating_avg or 0) / 5
        score = 0.30 * dist_score + 0.30 * price_score + 0.15 * auth_score + 0.15 * avail_score + 0.10 * rating_score
        gross = money((price or 0) * weight)
        transport = money(distance * settings.transport_inr_per_km)
        net = money(gross - transport)
        hours = round(distance / 25 + 0.5, 2)
        ranked.append(
            {
                "recycler_id": user.id,
                "business_name": profile.business_name,
                "licence_number": profile.licence_number,
                "verified": profile.status == "approved",
                "city": profile.city,
                "address": profile.address,
                "lat": profile.lat,
                "lng": profile.lng,
                "availability": profile.availability,
                "next_slot": profile.next_slot,
                "rating": round(profile.rating_avg or 0, 2),
                "rating_count": profile.rating_count,
                "reliability_score": round(profile.reliability_score or 0, 1),
                "distance_km": round(distance, 2),
                "price_per_kg": price,
                "gross": gross,
                "transport_cost": transport,
                "net_payout": net,
                "eta_hours": hours,
                "score": round(score, 4),
                "factors": {
                    "distance": round(dist_score, 3),
                    "price": round(price_score, 3),
                    "authorization": auth_score,
                    "availability": avail_score,
                    "rating": round(rating_score, 3),
                },
                "reason": (
                    f"{round(distance, 1)} km, "
                    f"{'₹' + str(price) + '/kg' if price else 'no offer'}, "
                    f"authorized, {profile.availability}, rating {round(profile.rating_avg or 0, 1)}"
                ),
            }
        )
    ranked.sort(key=lambda item: (-item["score"], -item["net_payout"]))
    return ranked


def comparison_for_lot(db: Session, lot: Lot) -> list[dict]:
    material = db.get(Material, lot.material_id)
    if lot.lat is None or lot.lng is None:
        return []
    rows = candidates(db, lot.lat, lot.lng, material, lot.weight_kg, None, None)
    for row in rows:
        override = lot_offer(db, row["recycler_id"], lot.id)
        if override:
            row["price_per_kg"] = override
            row["gross"] = money(override * lot.weight_kg)
            row["net_payout"] = money(row["gross"] - row["transport_cost"])
            row["reason"] = row["reason"] + " (lot offer)"
    rows.sort(key=lambda item: -(item["net_payout"] or 0))
    if rows:
        best = max(r["net_payout"] for r in rows)
        for row in rows:
            row["best"] = row["net_payout"] == best and best > 0
    return rows
