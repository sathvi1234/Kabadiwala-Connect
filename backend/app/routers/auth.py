from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import CollectorProfile, OtpChallenge, RecyclerDocument, RecyclerProfile, Referral, User, utcnow
from app.rate_limit import limit
from app.security import create_token, get_current_user, hash_password, verify_password
from app.services.alerts import ensure_auto_rules
from app.services.common import audit, material_by_code, now
from app.storage import save_upload
from datetime import timedelta
import json
import re
import secrets

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    phone: str = ""
    email: str = ""
    password: str = Field(min_length=8, max_length=100)


def _phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    if not re.fullmatch(r"\d{10}", digits):
        raise HTTPException(status_code=422, detail={"code": "invalid_phone"})
    return digits


def _lang(value: str) -> str:
    if value not in {"en", "hi", "mr"}:
        raise HTTPException(status_code=422, detail={"code": "invalid_language"})
    return value


def _consume_otp(db: Session, phone: str, code: str):
    row = (
        db.query(OtpChallenge)
        .filter(OtpChallenge.phone == phone, OtpChallenge.used.is_(False))
        .order_by(OtpChallenge.created_at.desc())
        .first()
    )
    if not row or row.code != code or row.expires_at < now():
        raise HTTPException(status_code=400, detail={"code": "invalid_otp"})
    row.used = True


def _referral_code() -> str:
    return secrets.token_hex(4).upper()


@router.post("/otp/request")
def request_otp(payload: dict, request: Request, db: Session = Depends(get_db)):
    limit(request, "otp", 5)
    phone = _phone(str(payload.get("phone", "")))
    settings = get_settings()
    code = settings.otp_dev_code if settings.is_dev else f"{secrets.randbelow(1000000):06d}"
    db.add(OtpChallenge(phone=phone, code=code, expires_at=now() + timedelta(minutes=10), created_at=utcnow()))
    db.commit()
    body = {"sent": True, "phone": phone}
    if settings.is_dev:
        body["dev_otp"] = code
    return body


@router.post("/login")
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)):
    limit(request, "login", 10)
    if payload.email.strip():
        user = db.query(User).filter(User.email == payload.email.strip().lower()).one_or_none()
    else:
        phone = _phone(payload.phone)
        user = db.query(User).filter(User.phone == phone).one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail={"code": "bad_credentials"})
    if not user.is_active:
        raise HTTPException(status_code=403, detail={"code": "inactive"})
    return {"token": create_token(user.id, user.role), "user": _public_user(user, db)}


class OtpLoginIn(BaseModel):
    phone: str
    otp: str


@router.post("/login/otp")
def login_otp(payload: OtpLoginIn, request: Request, db: Session = Depends(get_db)):
    limit(request, "login", 10)
    phone = _phone(payload.phone)
    _consume_otp(db, phone, payload.otp.strip())
    user = db.query(User).filter(User.phone == phone).one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail={"code": "bad_credentials"})
    db.commit()
    return {"token": create_token(user.id, user.role), "user": _public_user(user, db)}


class DemoIn(BaseModel):
    role: str


@router.post("/demo-login")
def demo_login(payload: DemoIn, request: Request, db: Session = Depends(get_db)):
    settings = get_settings()
    if not settings.demo_mode:
        raise HTTPException(status_code=403, detail={"code": "demo_disabled"})
    limit(request, "demo-login", 20)
    from app.services.demo import DEMO_PHONES

    phone = DEMO_PHONES.get(payload.role)
    if not phone:
        raise HTTPException(status_code=422, detail={"code": "bad_role"})
    user = db.query(User).filter(User.phone == phone, User.is_demo.is_(True), User.is_active.is_(True)).one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    return {"token": create_token(user.id, user.role), "user": _public_user(user, db)}


@router.post("/refresh")
def refresh_token(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"token": create_token(user.id, user.role), "user": _public_user(user, db)}


@router.post("/demo-reset")
def demo_reset(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    settings = get_settings()
    if not settings.demo_mode or not user.is_demo:
        raise HTTPException(status_code=403, detail={"code": "demo_locked"})
    limit(request, "demo-reset", 5)
    from app.services.demo import reset_demo_data

    result = reset_demo_data(db)
    audit(db, user, "demo_reset", "demo", user.id, result, request)
    db.commit()
    return result


def _public_user(user: User, db: Session) -> dict:
    data = {
        "id": user.id,
        "name": user.name,
        "phone": user.phone,
        "role": user.role,
        "preferred_language": user.preferred_language,
        "is_demo": bool(user.is_demo),
        "referral_code": user.referral_code,
        "created_at": user.created_at.isoformat(),
    }
    if user.role == "collector" and user.collector_profile:
        p = user.collector_profile
        data["profile"] = {
            "area": p.area,
            "city": p.city,
            "lat": p.lat,
            "lng": p.lng,
            "materials": p.materials or [],
            "emergency_contact": p.emergency_contact,
            "low_data_mode": p.low_data_mode,
            "voice_nav_enabled": p.voice_nav_enabled,
            "image_quality": p.image_quality,
            "has_photo": bool(p.profile_photo_path),
            "photo_path": p.profile_photo_path,
        }
    if user.role == "recycler" and user.recycler_profile:
        p = user.recycler_profile
        data["profile"] = {
            "business_name": p.business_name,
            "licence_number": p.licence_number,
            "address": p.address,
            "city": p.city,
            "lat": p.lat,
            "lng": p.lng,
            "materials": p.materials or [],
            "working_hours": p.working_hours or {},
            "status": p.status,
            "rejection_reason": p.rejection_reason,
            "availability": p.availability,
            "next_slot": p.next_slot,
            "rating": p.rating_avg,
            "reliability_score": p.reliability_score,
        }
    return data


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _public_user(user, db)


@router.patch("/me")
def patch_me(payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.is_demo and "password" in payload:
        raise HTTPException(status_code=403, detail={"code": "demo_locked"})
    if "preferred_language" in payload:
        user.preferred_language = _lang(payload["preferred_language"])
    if "name" in payload and str(payload["name"]).strip():
        user.name = str(payload["name"]).strip()[:200]
    db.commit()
    return _public_user(user, db)


@router.post("/register/collector")
async def register_collector(
    request: Request,
    name: str = Form(...),
    phone: str = Form(...),
    password: str = Form(...),
    otp: str = Form(...),
    preferred_language: str = Form("en"),
    area: str = Form(...),
    city: str = Form(...),
    materials: str = Form("[]"),
    lat: float | None = Form(None),
    lng: float | None = Form(None),
    referral_code: str = Form(""),
    emergency_contact: str = Form(""),
    profile_photo: UploadFile | None = File(None),
    id_proof: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    limit(request, "register", 8)
    if len(password) < 8:
        raise HTTPException(status_code=422, detail={"code": "weak_password"})
    phone_n = _phone(phone)
    _consume_otp(db, phone_n, otp.strip())
    if db.query(User).filter(User.phone == phone_n).first():
        raise HTTPException(status_code=409, detail={"code": "phone_taken"})
    try:
        codes = json.loads(materials) if materials else []
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail={"code": "bad_materials"}) from exc
    if not isinstance(codes, list) or not codes:
        raise HTTPException(status_code=422, detail={"code": "bad_materials"})
    for code in codes:
        material_by_code(db, code)
    lang = _lang(preferred_language)
    user = User(
        phone=phone_n,
        password_hash=hash_password(password),
        role="collector",
        name=name.strip()[:200],
        preferred_language=lang,
        referral_code=_referral_code(),
        created_at=utcnow(),
    )
    if referral_code.strip():
        referrer = db.query(User).filter(User.referral_code == referral_code.strip().upper()).one_or_none()
        if not referrer:
            raise HTTPException(status_code=422, detail={"code": "bad_referral"})
        user.referred_by_code = referrer.referral_code
    db.add(user)
    db.flush()
    photo_path = await save_upload(profile_photo, "photos", images_only=True, recompress=True) if profile_photo else None
    proof_path = await save_upload(id_proof, "proofs", images_only=False) if id_proof else None
    db.add(
        CollectorProfile(
            user_id=user.id,
            area=area.strip(),
            city=city.strip(),
            lat=lat,
            lng=lng,
            profile_photo_path=photo_path,
            id_proof_path=proof_path,
            materials=codes,
            emergency_contact=_phone(emergency_contact) if emergency_contact.strip() else None,
        )
    )
    if user.referred_by_code:
        referrer = db.query(User).filter(User.referral_code == user.referred_by_code).one()
        db.add(Referral(referrer_id=referrer.id, code=referrer.referral_code, referred_user_id=user.id, created_at=utcnow()))
    ensure_auto_rules(db, user.id, codes, city.strip())
    audit(db, user, "register_collector", "user", user.id, {"city": city}, request)
    db.commit()
    db.refresh(user)
    return {"token": create_token(user.id, user.role), "user": _public_user(user, db)}


@router.post("/register/recycler")
async def register_recycler(
    request: Request,
    name: str = Form(...),
    phone: str = Form(...),
    password: str = Form(...),
    otp: str = Form(...),
    preferred_language: str = Form("en"),
    business_name: str = Form(...),
    licence_number: str = Form(...),
    address: str = Form(...),
    city: str = Form(...),
    lat: float = Form(...),
    lng: float = Form(...),
    materials: str = Form("[]"),
    working_hours: str = Form("{}"),
    documents: list[UploadFile] | None = File(None),
    db: Session = Depends(get_db),
):
    limit(request, "register", 8)
    if len(password) < 8:
        raise HTTPException(status_code=422, detail={"code": "weak_password"})
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise HTTPException(status_code=422, detail={"code": "bad_gps"})
    phone_n = _phone(phone)
    _consume_otp(db, phone_n, otp.strip())
    if db.query(User).filter(User.phone == phone_n).first():
        raise HTTPException(status_code=409, detail={"code": "phone_taken"})
    try:
        codes = json.loads(materials)
        hours = json.loads(working_hours)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail={"code": "bad_materials"}) from exc
    if not codes:
        raise HTTPException(status_code=422, detail={"code": "bad_materials"})
    for code in codes:
        material_by_code(db, code)
    user = User(
        phone=phone_n,
        password_hash=hash_password(password),
        role="recycler",
        name=name.strip()[:200],
        preferred_language=_lang(preferred_language),
        referral_code=_referral_code(),
        created_at=utcnow(),
    )
    db.add(user)
    db.flush()
    db.add(
        RecyclerProfile(
            user_id=user.id,
            business_name=business_name.strip(),
            licence_number=licence_number.strip(),
            address=address.strip(),
            city=city.strip(),
            lat=lat,
            lng=lng,
            materials=codes,
            working_hours=hours if isinstance(hours, dict) else {},
            status="pending",
            availability="offline",
        )
    )
    for doc in documents or []:
        if not doc.filename:
            continue
        path = await save_upload(doc, "documents")
        db.add(RecyclerDocument(recycler_id=user.id, doc_type="licence", file_path=path, created_at=utcnow()))
    audit(db, user, "register_recycler", "user", user.id, {"business": business_name}, request)
    db.commit()
    db.refresh(user)
    return {"token": create_token(user.id, user.role), "user": _public_user(user, db)}
