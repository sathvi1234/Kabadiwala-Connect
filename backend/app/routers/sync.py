from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Lot, PriceFeed, SyncQueueLog, User, utcnow
from app.routers.lots import LotIn, attach_photo, create_lot_record, dump_lot, photo_from_b64
from app.security import require_roles

router = APIRouter(prefix="/api/sync", tags=["sync"])


class SyncOp(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=64)
    type: str
    payload: dict
    photo_base64: str | None = None


class SyncIn(BaseModel):
    operations: list[SyncOp]


@router.post("/push")
def push(body: SyncIn, user: User = Depends(require_roles("collector")), db: Session = Depends(get_db)):
    results = []
    for op in body.operations:
        try:
            if op.type == "create_lot":
                data = LotIn(**{**op.payload, "idempotency_key": op.idempotency_key, "offline": True})
                lot, replay = create_lot_record(db, user, data)
                if op.photo_base64 and not replay:
                    attach_photo(db, lot, photo_from_b64(op.photo_base64), "collection")
                db.add(SyncQueueLog(user_id=user.id, idempotency_key=op.idempotency_key, entity="lot", status="synced", created_at=utcnow()))
                results.append({"idempotency_key": op.idempotency_key, "status": "synced", "conflict": None, "lot": dump_lot(db, lot, user), "replayed": replay})
            elif op.type == "update_lot_draft":
                lot = db.query(Lot).filter(Lot.idempotency_key == op.idempotency_key, Lot.collector_id == user.id).one_or_none()
                if not lot:
                    results.append({"idempotency_key": op.idempotency_key, "status": "failed", "error": "not_found"})
                    continue
                if lot.status not in {"open", "draft"}:
                    results.append({"idempotency_key": op.idempotency_key, "status": "synced", "conflict": "server_wins", "lot": dump_lot(db, lot, user)})
                    continue
                if "weight" in op.payload:
                    lot.weight_kg = float(op.payload["weight"])
                    lot.input_weight = float(op.payload["weight"])
                lot.updated_at = utcnow()
                results.append({"idempotency_key": op.idempotency_key, "status": "synced", "conflict": "client_wins", "lot": dump_lot(db, lot, user)})
            elif op.type in {"price", "price_feed"}:
                row = db.query(PriceFeed).order_by(PriceFeed.recorded_on.desc()).first()
                results.append({"idempotency_key": op.idempotency_key, "status": "synced", "conflict": "server_wins", "price_id": row.id if row else None})
            else:
                raise HTTPException(status_code=422, detail={"code": "bad_sync_type"})
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {"code": "sync_failed"}
            db.add(SyncQueueLog(user_id=user.id, idempotency_key=op.idempotency_key, entity=op.type, status="failed", error=detail.get("code", ""), created_at=utcnow()))
            results.append({"idempotency_key": op.idempotency_key, "status": "failed", "error": detail.get("code")})
    db.commit()
    return {"results": results}
