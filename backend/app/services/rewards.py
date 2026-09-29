from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Badge, Handover, LedgerEntry, Lot, Referral, User, UserBadge
from app.services.common import money, notify, now


def current_balance(db: Session, collector_id: str) -> float:
    last = (
        db.query(LedgerEntry)
        .filter(LedgerEntry.collector_id == collector_id)
        .order_by(LedgerEntry.created_at.desc())
        .first()
    )
    return last.balance_after if last else 0.0


def add_ledger(db: Session, collector_id: str, entry_type: str, amount: float, note: str, transaction_id: str | None = None):
    balance = current_balance(db, collector_id)
    signed = amount if entry_type == "credit" else -amount
    entry = LedgerEntry(
        collector_id=collector_id,
        transaction_id=transaction_id,
        entry_type=entry_type,
        amount=money(amount),
        balance_after=money(balance + signed),
        note=note,
        created_at=now(),
    )
    db.add(entry)
    db.flush()
    return entry


def verified_handover_count(db: Session, collector_id: str) -> int:
    return (
        db.query(Handover)
        .join(Lot, Lot.id == Handover.lot_id)
        .filter(
            Lot.collector_id == collector_id,
            Handover.collector_confirmed_at.isnot(None),
            Handover.recycler_confirmed_at.isnot(None),
        )
        .count()
    )


def award_badges(db: Session, collector: User):
    count = verified_handover_count(db, collector.id)
    badges = db.query(Badge).order_by(Badge.threshold.asc()).all()
    owned = {row.badge_id for row in db.query(UserBadge).filter(UserBadge.user_id == collector.id).all()}
    awarded = []
    for badge in badges:
        if count >= badge.threshold and badge.id not in owned:
            db.add(UserBadge(user_id=collector.id, badge_id=badge.id, awarded_at=now()))
            notify(db, collector.id, badge.name, badge.description, "badge", {"code": badge.code})
            awarded.append(badge.code)
    return awarded


def reward_referral(db: Session, collector: User):
    if not collector.referred_by_code:
        return None
    referral = db.query(Referral).filter(Referral.referred_user_id == collector.id, Referral.rewarded.is_(False)).one_or_none()
    if not referral:
        return None
    if verified_handover_count(db, collector.id) < 1:
        return None
    bonus = get_settings().referral_bonus_inr
    add_ledger(db, referral.referrer_id, "credit", bonus, f"Referral bonus for {collector.name}")
    referral.rewarded = True
    referral.rewarded_at = now()
    notify(db, referral.referrer_id, "Referral reward", f"₹{bonus:.0f} credited for a verified handover.", "referral")
    return referral
