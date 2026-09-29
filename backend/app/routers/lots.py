import base64
import binascii

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Lot, LotEvent, LotPhoto, Material, SyncQueueLog, User, utcnow
from app.security import get_current_user, require_roles
from app.services.common import audit, material_by_code, money, parse_dt, public_code
from app.services.duplicates import find_duplicate
from app.services.images import dhash
from app.services.pricing import estimate_value
from app.storage import absolute_path, recompress_image, save_upload
from app.config import get_settings
import qrcode
import io

router = APIRouter(prefix="/api/lots", tags=["lots"])


class LotIn(BaseModel):
    material_code: str
    weight: float = Field(gt=0, lt=20000)
    unit: str = "kg"
    lat: float | None = None
    lng: float | None = None
    city: str = ""
    captured_at: str | None = None
    idempotency_key: str | None = Field(default=None, max_length=64)
    offline: bool = False
    ai_material: str | None = None
    ai_confidence: float | None = None
    components: list[dict] = []
    condition: str | None = None
    condition_note: str | None = None


def _weight_kg(weight: float, unit: str) -> float:
    if unit not in {"kg", "g"}:
        raise HTTPException(status_code=422, detail={"code": "bad_unit"})
    kg = weight / 1000 if unit == "g" else weight
    if kg <= 0 or kg > 20000:
        raise HTTPException(status_code=422, detail={"code": "bad_weight"})
    return kg


def dump_lot(db: Session, lot: Lot, viewer: User | None = None) -> dict:
    material = lot.material or db.get(Material, lot.material_id)
    show_collector = viewer and viewer.role in {"admin", "recycler"} or (viewer and viewer.id == lot.collector_id)
    collector = db.get(User, lot.collector_id) if show_collector else None
    return {
        "id": lot.id,
        "public_id": lot.public_id,
        "material": material.code if material else "",
        "material_name": {"en": material.name_en, "hi": material.name_hi, "mr": material.name_mr} if material else {},
        "components": lot.components or [],
        "weight_kg": lot.weight_kg,
        "input_weight": lot.input_weight,
        "input_unit": lot.input_unit,
        "lat": lot.lat,
        "lng": lot.lng,
        "city": lot.city,
        "captured_at": lot.captured_at.isoformat(),
        "status": lot.status,
        "estimated_value": lot.estimated_value,
        "price_per_kg": lot.price_per_kg,
        "price_source": lot.price_source,
        "price_date": lot.price_date,
        "price_market": lot.price_market,
        "flags": lot.flags or {},
        "ai_material": lot.ai_material,
        "ai_confidence": lot.ai_confidence,
        "condition": lot.condition,
        "condition_note": lot.condition_note,
        "duplicate_of": lot.duplicate_of,
        "duplicate_score": lot.duplicate_score,
        "duplicate_status": lot.duplicate_status,
        "offline_origin": lot.offline_origin,
        "created_at": lot.created_at.isoformat(),
        "collector_name": collector.name if collector else None,
        "photos": [
            {"id": p.id, "kind": p.kind, "path": p.path, "created_at": p.created_at.isoformat()}
            for p in lot.photos
        ],
        "events": [
            {
                "type": e.event_type,
                "note": e.note,
                "actor_role": e.actor_role,
                "at": e.created_at.isoformat(),
            }
            for e in sorted(lot.events, key=lambda item: item.created_at)
        ],
    }


def create_lot_record(db: Session, user: User, payload: LotIn, request: Request | None = None) -> tuple[Lot, bool]:
    if payload.idempotency_key:
        existing = db.query(Lot).filter(Lot.idempotency_key == payload.idempotency_key).one_or_none()
        if existing:
            return existing, True
    if payload.lat is not None and not -90 <= payload.lat <= 90:
        raise HTTPException(status_code=422, detail={"code": "bad_gps"})
    if payload.lng is not None and not -180 <= payload.lng <= 180:
        raise HTTPException(status_code=422, detail={"code": "bad_gps"})
    material = material_by_code(db, payload.material_code)
    kg = _weight_kg(payload.weight, payload.unit)
    city = payload.city or (user.collector_profile.city if user.collector_profile else "")
    quote = estimate_value(db, material, kg, city)
    captured = parse_dt(payload.captured_at)
    from app.services.verification import collection_flags

    lot = Lot(
        public_id=public_code("LOT"),
        collector_id=user.id,
        material_id=material.id,
        components=payload.components or [],
        weight_kg=kg,
        input_weight=payload.weight,
        input_unit=payload.unit,
        lat=payload.lat,
        lng=payload.lng,
        city=city,
        captured_at=captured,
        status="open",
        estimated_value=quote["value"],
        price_per_kg=quote["price_per_kg"],
        price_source=quote["source"],
        price_date=quote["date"],
        price_market=quote["market"],
        idempotency_key=payload.idempotency_key,
        flags=collection_flags(payload.lat, payload.lng, captured, False, payload.offline),
        ai_material=payload.ai_material,
        ai_confidence=payload.ai_confidence,
        condition=payload.condition,
        condition_note=payload.condition_note,
        offline_origin=payload.offline,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    for _ in range(5):
        if not db.query(Lot).filter(Lot.public_id == lot.public_id).first():
            break
        lot.public_id = public_code("LOT")
    db.add(lot)
    db.flush()
    db.add(
        LotEvent(
            lot_id=lot.id,
            event_type="collection",
            actor_id=user.id,
            actor_role="collector",
            note=f"{material.code} {kg} kg",
            lat=payload.lat,
            lng=payload.lng,
            created_at=captured,
        )
    )
    audit(db, user, "create_lot", "lot", lot.public_id, {"offline": payload.offline}, request)
    return lot, False


def attach_photo(db: Session, lot: Lot, data: bytes, kind: str = "collection"):
    settings = get_settings()
    data, _ext = recompress_image(data, settings.max_image_kb * 1024)
    import uuid
    from app.storage import upload_root

    name = f"{uuid.uuid4().hex}.webp"
    folder = upload_root() / "photos"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(data)
    phash = dhash(data)
    photo = LotPhoto(lot_id=lot.id, kind=kind, path=f"photos/{name}", phash=phash, created_at=utcnow())
    db.add(photo)
    db.flush()
    flags = dict(lot.flags or {})
    flags["photo_present"] = True
    lot.flags = flags
    dup = find_duplicate(db, lot, phash)
    if dup and lot.duplicate_status == "none":
        lot.duplicate_of = dup["lot_id"]
        lot.duplicate_score = dup["score"]
        lot.duplicate_status = "flagged"
    return photo


@router.post("")
def create_lot(payload: LotIn, request: Request, user: User = Depends(require_roles("collector")), db: Session = Depends(get_db)):
    lot, replay = create_lot_record(db, user, payload, request)
    if payload.idempotency_key:
        db.add(
            SyncQueueLog(
                user_id=user.id,
                idempotency_key=payload.idempotency_key,
                entity="lot",
                status="synced",
                created_at=utcnow(),
            )
        )
    db.commit()
    db.refresh(lot)
    body = dump_lot(db, lot, user)
    body["replayed"] = replay
    return body


@router.get("")
def list_lots(
    status: str | None = None,
    material: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Lot)
    if user.role == "collector":
        q = q.filter(Lot.collector_id == user.id)
    elif user.role == "recycler":
        from app.models import Pickup

        ids = [p.lot_id for p in db.query(Pickup).filter(Pickup.recycler_id == user.id).all()]
        q = q.filter(Lot.id.in_(ids or ["none"]))
    if status:
        q = q.filter(Lot.status == status)
    if material:
        mat = material_by_code(db, material)
        q = q.filter(Lot.material_id == mat.id)
    rows = q.order_by(Lot.created_at.desc()).limit(200).all()
    return [dump_lot(db, lot, user) for lot in rows]


@router.get("/{lot_id}")
def get_lot(lot_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lot = _load(db, lot_id)
    _can_view(db, lot, user)
    return dump_lot(db, lot, user)


def _load(db: Session, lot_id: str) -> Lot:
    lot = db.query(Lot).filter((Lot.id == lot_id) | (Lot.public_id == lot_id)).one_or_none()
    if not lot:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    return lot


def _can_view(db: Session, lot: Lot, user: User):
    if user.role == "admin" or lot.collector_id == user.id:
        return
    if user.role == "recycler":
        from app.models import Pickup

        if db.query(Pickup).filter(Pickup.lot_id == lot.id, Pickup.recycler_id == user.id).first():
            return
        if user.recycler_profile and user.recycler_profile.status == "approved":
            return
    raise HTTPException(status_code=403, detail={"code": "forbidden"})


@router.post("/{lot_id}/photos")
async def add_photo(
    lot_id: str,
    kind: str = "collection",
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lot = _load(db, lot_id)
    if user.role == "collector" and lot.collector_id != user.id:
        raise HTTPException(status_code=403, detail={"code": "forbidden"})
    if kind not in {"collection", "handover"}:
        raise HTTPException(status_code=422, detail={"code": "bad_kind"})
    saved = await save_upload(file, "photos", images_only=True, recompress=False)
    raw = absolute_path(saved).read_bytes()
    absolute_path(saved).unlink(missing_ok=True)
    attach_photo(db, lot, raw, kind)
    lot.updated_at = utcnow()
    db.commit()
    db.refresh(lot)
    return dump_lot(db, lot, user)


@router.post("/{lot_id}/duplicate/{action}")
def duplicate_action(lot_id: str, action: str, user: User = Depends(require_roles("collector")), db: Session = Depends(get_db)):
    lot = _load(db, lot_id)
    if lot.collector_id != user.id:
        raise HTTPException(status_code=403, detail={"code": "forbidden"})
    if action not in {"confirm", "dismiss"}:
        raise HTTPException(status_code=422, detail={"code": "bad_action"})
    lot.duplicate_status = "confirmed" if action == "confirm" else "dismissed"
    db.commit()
    return dump_lot(db, lot, user)


@router.get("/{lot_id}/qr")
def lot_qr(lot_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lot = _load(db, lot_id)
    _can_view(db, lot, user)
    image = qrcode.make(lot.public_id)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


@router.get("/{lot_id}/comparison")
def comparison(lot_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.services.matching import comparison_for_lot

    lot = _load(db, lot_id)
    _can_view(db, lot, user)
    rows = comparison_for_lot(db, lot)
    return {"lot_id": lot.public_id, "offers": rows}


class EstimateIn(BaseModel):
    material_code: str
    weight: float = Field(gt=0)
    unit: str = "kg"
    city: str = ""


@router.post("/estimate")
def estimate(payload: EstimateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    material = material_by_code(db, payload.material_code)
    kg = _weight_kg(payload.weight, payload.unit)
    city = payload.city or (user.collector_profile.city if user.collector_profile else "Hyderabad")
    quote = estimate_value(db, material, kg, city)
    quote["weight_kg"] = kg
    quote["value"] = money(quote["value"])
    return quote


def photo_from_b64(payload: str) -> bytes:
    try:
        raw = payload.split(",", 1)[-1]
        return base64.b64decode(raw)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail={"code": "bad_file_type"}) from exc
