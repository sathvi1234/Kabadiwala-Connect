from sqlalchemy.orm import Session

from app.models import Dispute, Handover, Pickup, RatingFeedback, Transaction


def reliability(db: Session, recycler_id: str) -> dict:
    pickups = db.query(Pickup).filter(Pickup.recycler_id == recycler_id).all()
    accepted = [p for p in pickups if p.status in {"accepted", "completed"}]
    on_time = 1.0
    if accepted:
        on_time = sum(1 for p in accepted if p.status in {"accepted", "completed"}) / len(pickups or [1])
    handovers = (
        db.query(Handover)
        .join(Pickup, Pickup.lot_id == Handover.lot_id)
        .filter(Pickup.recycler_id == recycler_id, Pickup.status.in_(["accepted", "completed"]))
        .all()
    )
    mismatches = sum(1 for h in handovers if (h.flags or {}).get("weight_mismatch"))
    weight_ok = 1 - (mismatches / len(handovers) if handovers else 0)
    tx = db.query(Transaction).filter(Transaction.recycler_id == recycler_id).all()
    delayed = sum(1 for t in tx if t.status != "paid")
    pay_ok = 1 - (delayed / len(tx) if tx else 0)
    ratings = db.query(RatingFeedback).filter(RatingFeedback.recycler_id == recycler_id).all()
    rating = (sum(r.stars for r in ratings) / len(ratings) / 5) if ratings else 0.6
    disputes = db.query(Dispute).filter(Dispute.against_user == recycler_id).count()
    dispute_ok = max(0, 1 - disputes / 10)
    score = round((on_time * 30 + weight_ok * 20 + pay_ok * 20 + rating * 20 + dispute_ok * 10), 1)
    return {
        "score": score,
        "factors": {
            "on_time_pickups": round(on_time, 2),
            "weight_ok": round(weight_ok, 2),
            "payment_ok": round(pay_ok, 2),
            "rating": round(rating, 2),
            "dispute_ok": round(dispute_ok, 2),
        },
    }
