import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Lot, Material, PaymentLine, Receipt, Transaction, User, utcnow
from app.security import get_current_user, require_roles
from app.services.common import audit
from app.services.payments import new_receipt_number, record_payment
from app.services.pdfs import build_certificate_pdf, build_receipt_pdf
from app.services.rewards import current_balance
from app.storage import absolute_path

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


class PayIn(BaseModel):
    amount: float = Field(gt=0)
    mode: str
    reference: str = ""


def _visible(db: Session, user: User):
    q = db.query(Transaction)
    if user.role == "collector":
        q = q.filter(Transaction.collector_id == user.id)
    elif user.role == "recycler":
        q = q.filter(Transaction.recycler_id == user.id)
    return q


def dump_tx(db: Session, tx: Transaction) -> dict:
    lot = db.get(Lot, tx.lot_id)
    material = lot.material.code if lot and lot.material else ""
    recycler = db.get(User, tx.recycler_id)
    collector = db.get(User, tx.collector_id)
    lines = db.query(PaymentLine).filter(PaymentLine.transaction_id == tx.id).order_by(PaymentLine.created_at.asc()).all()
    return {
        "id": tx.id,
        "public_id": tx.public_id,
        "lot_id": lot.public_id if lot else tx.lot_id,
        "material": material,
        "collector_name": collector.name if collector else "",
        "recycler_name": recycler.recycler_profile.business_name if recycler and recycler.recycler_profile else "",
        "recycler_id": tx.recycler_id,
        "amount": tx.amount,
        "paid_amount": tx.paid_amount,
        "pending_amount": round(tx.amount - tx.paid_amount, 2),
        "mode": tx.mode,
        "status": tx.status,
        "created_at": tx.created_at.isoformat(),
        "lines": [{"amount": line.amount, "mode": line.mode, "reference": line.reference, "at": line.created_at.isoformat()} for line in lines],
    }


@router.get("")
def list_tx(
    status: str | None = None,
    material: str | None = None,
    recycler_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = _visible(db, user)
    if status:
        q = q.filter(Transaction.status == status)
    if recycler_id:
        q = q.filter(Transaction.recycler_id == recycler_id)
    rows = q.order_by(Transaction.created_at.desc()).limit(500).all()
    dumped = [dump_tx(db, tx) for tx in rows]
    if material:
        dumped = [row for row in dumped if row["material"] == material]
    if date_from:
        dumped = [row for row in dumped if row["created_at"] >= date_from]
    if date_to:
        dumped = [row for row in dumped if row["created_at"][:10] <= date_to]
    return dumped


@router.get("/export.csv")
def export_csv(
    status: str | None = None,
    material: str | None = None,
    recycler_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = list_tx(status, material, recycler_id, date_from, date_to, user, db)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["public_id", "lot_id", "material", "recycler_name", "amount", "paid_amount", "mode", "status", "created_at"])
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row[k] for k in writer.fieldnames})
    return Response(content=buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=transactions.csv"})


@router.get("/ledger")
def ledger(user: User = Depends(require_roles("collector")), db: Session = Depends(get_db)):
    from app.models import LedgerEntry

    rows = db.query(LedgerEntry).filter(LedgerEntry.collector_id == user.id).order_by(LedgerEntry.created_at.asc()).all()
    return {
        "balance": current_balance(db, user.id),
        "entries": [
            {
                "id": row.id,
                "type": row.entry_type,
                "amount": row.amount,
                "balance_after": row.balance_after,
                "note": row.note,
                "at": row.created_at.isoformat(),
            }
            for row in rows
        ],
    }


@router.post("/{tx_id}/pay")
def pay(tx_id: str, payload: PayIn, request: Request, user: User = Depends(require_roles("recycler", "admin")), db: Session = Depends(get_db)):
    tx = db.query(Transaction).filter((Transaction.id == tx_id) | (Transaction.public_id == tx_id)).one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    if user.role == "recycler" and tx.recycler_id != user.id:
        raise HTTPException(status_code=403, detail={"code": "forbidden"})
    record_payment(db, tx, payload.amount, payload.mode, payload.reference, user)
    audit(db, user, "payment", "transaction", tx.public_id, payload.model_dump(), request)
    db.commit()
    return dump_tx(db, tx)


@router.post("/{tx_id}/receipt")
def receipt(tx_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tx = db.query(Transaction).filter((Transaction.id == tx_id) | (Transaction.public_id == tx_id)).one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    if user.role != "admin" and user.id not in {tx.collector_id, tx.recycler_id}:
        raise HTTPException(status_code=403, detail={"code": "forbidden"})
    existing = db.query(Receipt).filter(Receipt.transaction_id == tx.id).order_by(Receipt.created_at.desc()).first()
    lot = db.get(Lot, tx.lot_id)
    number = existing.receipt_number if existing else new_receipt_number()
    rel = existing.pdf_path if existing else f"receipts/{number}.pdf"
    verify = f"/verify/{lot.public_id if lot else ''}"
    build_receipt_pdf(
        rel,
        number,
        [
            ("Receipt", number),
            ("Transaction", tx.public_id),
            ("Lot", lot.public_id if lot else ""),
            ("Amount due", f"INR {tx.amount:.2f}"),
            ("Paid", f"INR {tx.paid_amount:.2f}"),
            ("Mode", tx.mode or ""),
            ("Status", tx.status),
        ],
        verify,
    )
    if not existing:
        db.add(Receipt(transaction_id=tx.id, receipt_number=number, pdf_path=rel, created_at=utcnow()))
        db.commit()
    path = absolute_path(rel)
    return StreamingResponse(path.open("rb"), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{number}.pdf"'})


@router.get("/{tx_id}/certificate")
def certificate(tx_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.models import Handover

    tx = db.query(Transaction).filter((Transaction.id == tx_id) | (Transaction.public_id == tx_id)).one_or_none()
    if not tx or (user.role != "admin" and user.id not in {tx.collector_id, tx.recycler_id}):
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    lot = db.get(Lot, tx.lot_id)
    handover = db.query(Handover).filter(Handover.lot_id == lot.id).one_or_none()
    rel = f"certificates/{lot.public_id}.pdf"
    flags = handover.flags if handover else {}
    build_certificate_pdf(
        rel,
        lot.public_id,
        [
            ("Material", lot.material.code if lot.material else ""),
            ("Declared kg", str(lot.weight_kg)),
            ("Verified kg", str(handover.weight_verified_kg if handover else "")),
            ("Difference kg", str(handover.weight_difference_kg if handover else "")),
            ("GPS", "yes" if flags.get("gps_present") else "no"),
            ("Photo", "yes" if flags.get("photo_present") else "no"),
            ("Time ok", "yes" if flags.get("time_ok") else "no"),
            ("Distance flag", "yes" if flags.get("distance_suspicious") else "no"),
            ("Status", lot.status),
        ],
        f"/verify/{lot.public_id}",
    )
    if handover:
        handover.certificate_path = rel
        db.commit()
    path = absolute_path(rel)
    return StreamingResponse(path.open("rb"), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{lot.public_id}-certificate.pdf"'})
