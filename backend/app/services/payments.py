import secrets

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import (
    Handover,
    Lot,
    LotEvent,
    PaymentLine,
    RecyclerOffer,
    Transaction,
    User,
    utcnow,
)
from app.services.common import money, notify, public_code
from app.services.matching import lot_offer, standing_price
from app.services.rewards import add_ledger, award_badges, reward_referral


def agreed_price(db: Session, lot: Lot, recycler_id: str) -> float:
    return lot_offer(db, recycler_id, lot.id) or standing_price(db, recycler_id, lot.material_id) or lot.price_per_kg or 0


def ensure_transaction(db: Session, lot: Lot, recycler_id: str, weight: float) -> Transaction:
    existing = db.query(Transaction).filter(Transaction.lot_id == lot.id).one_or_none()
    if existing:
        return existing
    price = agreed_price(db, lot, recycler_id)
    tx = Transaction(
        public_id=public_code("TX"),
        lot_id=lot.id,
        collector_id=lot.collector_id,
        recycler_id=recycler_id,
        amount=money(price * weight),
        paid_amount=0,
        status="pending",
        created_at=utcnow(),
    )
    for _ in range(5):
        clash = db.query(Transaction).filter(Transaction.public_id == tx.public_id).first()
        if not clash:
            break
        tx.public_id = public_code("TX")
    db.add(tx)
    db.flush()
    notify(db, lot.collector_id, "Handover recorded", f"{lot.public_id} is ready for payment.", "handover", {"lot": lot.public_id})
    notify(db, recycler_id, "Handover recorded", f"Confirm payment for {lot.public_id}.", "handover", {"lot": lot.public_id})
    return tx


def finalize_handover(db: Session, lot: Lot, handover: Handover, recycler_id: str):
    if not (handover.collector_confirmed_at and handover.recycler_confirmed_at):
        lot.status = "handover_pending"
        return None
    weight = handover.weight_verified_kg or lot.weight_kg
    lot.status = "handed_over"
    lot.flags = {**(lot.flags or {}), **(handover.flags or {})}
    db.add(
        LotEvent(
            lot_id=lot.id,
            event_type="handover",
            actor_id=recycler_id,
            actor_role="recycler",
            note="Both parties confirmed",
            lat=handover.lat,
            lng=handover.lng,
            meta={"weight_verified_kg": weight, "difference": handover.weight_difference_kg},
            created_at=utcnow(),
        )
    )
    tx = ensure_transaction(db, lot, recycler_id, weight)
    collector = db.get(User, lot.collector_id)
    award_badges(db, collector)
    reward_referral(db, collector)
    return tx


def record_payment(db: Session, tx: Transaction, amount: float, mode: str, reference: str, actor: User):
    if mode not in {"cash", "upi", "bank"}:
        raise HTTPException(status_code=422, detail={"code": "bad_payment_mode"})
    if amount <= 0:
        raise HTTPException(status_code=422, detail={"code": "bad_amount"})
    if mode in {"upi", "bank"} and not reference.strip():
        raise HTTPException(status_code=422, detail={"code": "reference_required"})
    remaining = money(tx.amount - tx.paid_amount)
    if amount - remaining > 0.05:
        raise HTTPException(status_code=422, detail={"code": "over_payment"})
    db.add(PaymentLine(transaction_id=tx.id, amount=money(amount), mode=mode, reference=reference.strip(), created_at=utcnow()))
    tx.paid_amount = money(tx.paid_amount + amount)
    tx.mode = mode
    tx.status = "paid" if tx.paid_amount + 0.009 >= tx.amount else "partial"
    add_ledger(db, tx.collector_id, "credit", amount, f"{mode.upper()} for {tx.public_id}", tx.id)
    lot = db.get(Lot, tx.lot_id)
    if lot and tx.status == "paid" and lot.status == "handed_over":
        lot.status = "processing"
        db.add(LotEvent(lot_id=lot.id, event_type="payment", actor_id=actor.id, actor_role=actor.role, note=f"{mode} {amount}", created_at=utcnow()))
    elif lot:
        db.add(LotEvent(lot_id=lot.id, event_type="payment", actor_id=actor.id, actor_role=actor.role, note=f"partial {mode} {amount}", created_at=utcnow()))
    return tx


def new_receipt_number() -> str:
    return "RC-" + secrets.token_hex(4).upper()
