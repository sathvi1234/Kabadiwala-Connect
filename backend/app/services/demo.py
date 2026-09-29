"""Demo accounts, seeded lot ids, and a reversible reset of extra demo lots."""

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    Dispute,
    DisputeEvidence,
    Handover,
    LedgerEntry,
    Lot,
    LotEvent,
    LotPhoto,
    PaymentLine,
    Pickup,
    RatingFeedback,
    Receipt,
    RecyclerOffer,
    Transaction,
    User,
    utcnow,
)

DEMO_PHONES = {
    "collector": "9000000001",
    "recycler": "9000000011",
    "admin": "9999999999",
}


def seeded_public_ids() -> set[str]:
    pairs = [("PCB", 12), ("Aluminium", 2), ("Cable", 0), ("Battery", 1), ("Copper", 6)]
    found = set()
    for code, days in pairs:
        recorded = date.today() - timedelta(days=days)
        found.add(f"LOT-{recorded.strftime('%Y%m%d')}-{code[:3].upper()}{days:02d}")
    return found


def reset_demo_data(db: Session) -> dict:
    keep = seeded_public_ids()
    demo_ids = [row.id for row in db.query(User).filter(User.is_demo.is_(True), User.role == "collector").all()]
    extra = db.query(Lot).filter(Lot.collector_id.in_(demo_ids), Lot.public_id.notin_(keep)).all() if demo_ids else []
    removed = 0
    for lot in extra:
        tx_ids = [tx.id for tx in db.query(Transaction).filter(Transaction.lot_id == lot.id).all()]
        if tx_ids:
            db.query(PaymentLine).filter(PaymentLine.transaction_id.in_(tx_ids)).delete(synchronize_session=False)
            db.query(LedgerEntry).filter(LedgerEntry.transaction_id.in_(tx_ids)).delete(synchronize_session=False)
            db.query(Receipt).filter(Receipt.transaction_id.in_(tx_ids)).delete(synchronize_session=False)
            db.query(Transaction).filter(Transaction.id.in_(tx_ids)).delete(synchronize_session=False)
        dispute_ids = [row.id for row in db.query(Dispute).filter(Dispute.lot_id == lot.id).all()]
        if dispute_ids:
            db.query(DisputeEvidence).filter(DisputeEvidence.dispute_id.in_(dispute_ids)).delete(synchronize_session=False)
            db.query(Dispute).filter(Dispute.id.in_(dispute_ids)).delete(synchronize_session=False)
        db.query(RatingFeedback).filter(RatingFeedback.lot_id == lot.id).delete(synchronize_session=False)
        db.query(Handover).filter(Handover.lot_id == lot.id).delete(synchronize_session=False)
        db.query(Pickup).filter(Pickup.lot_id == lot.id).delete(synchronize_session=False)
        db.query(LotPhoto).filter(LotPhoto.lot_id == lot.id).delete(synchronize_session=False)
        db.query(LotEvent).filter(LotEvent.lot_id == lot.id).delete(synchronize_session=False)
        db.query(RecyclerOffer).filter(RecyclerOffer.lot_id == lot.id).delete(synchronize_session=False)
        db.delete(lot)
        removed += 1
    pending = db.query(User).filter(User.phone == "9000000014").one_or_none()
    if pending and pending.recycler_profile:
        profile = pending.recycler_profile
        profile.status = "pending"
        profile.availability = "offline"
        profile.rejection_reason = None
        db.add(profile)
    db.flush()
    return {"removed_lots": removed, "kept_lots": sorted(keep)}


def maybe_nightly_reset(db: Session) -> None:
    now = datetime.now()
    if now.hour != 3:
        return
    key = now.date().isoformat()
    already = db.query(AuditLog).filter(AuditLog.action == "demo_nightly_reset", AuditLog.entity_id == key).first()
    if already:
        return
    reset_demo_data(db)
    db.add(AuditLog(actor_id=None, action="demo_nightly_reset", entity_type="demo", entity_id=key, detail={}, ip="", created_at=utcnow()))
