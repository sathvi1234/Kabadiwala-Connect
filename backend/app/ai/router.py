from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.predict import abnormal, forecast
from app.ai.provider import condition, identify, mixed
from app.ai.safety_kb import answer as safety_answer
from app.ai.voice import detect_intent, detect_material, llm_intent
from app.database import get_db
from app.models import Lot, Material, PriceFeed, RecyclerOffer, Transaction, User
from app.security import get_current_user, get_optional_user, require_roles
from app.services.common import material_by_code, money
from app.services.matching import candidates, comparison_for_lot
from app.services.pricing import estimate_value, history
from app.services.reliability import reliability

router = APIRouter(prefix="/ai", tags=["ai"])


async def _bytes(file: UploadFile) -> bytes:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail={"code": "empty_file"})
    return data


@router.post("/identify")
async def identify_route(file: UploadFile = File(...), user: User = Depends(get_current_user)):
    return identify(await _bytes(file))


@router.post("/condition")
async def condition_route(file: UploadFile = File(...), user: User = Depends(get_current_user)):
    return condition(await _bytes(file))


@router.post("/mixed-scrap")
async def mixed_route(file: UploadFile = File(...), user: User = Depends(get_current_user)):
    return mixed(await _bytes(file))


class EstimateIn(BaseModel):
    material_code: str
    weight: float = Field(gt=0)
    unit: str = "kg"
    city: str = ""


@router.post("/estimate-price")
def estimate_price(payload: EstimateIn, db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)):
    mat = material_by_code(db, payload.material_code)
    kg = payload.weight / 1000 if payload.unit == "g" else payload.weight
    city = payload.city or (user.collector_profile.city if user and user.collector_profile else "Hyderabad")
    quote = estimate_value(db, mat, kg, city)
    return {**quote, "material": mat.code, "weight_kg": kg, "provider": "price_feed_band"}


class RecommendIn(BaseModel):
    material_code: str | None = None
    weight: float | None = None
    lat: float | None = None
    lng: float | None = None
    lot_id: str | None = None


@router.post("/recommend-recycler")
def recommend(payload: RecommendIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.lot_id:
        lot = db.query(Lot).filter((Lot.id == payload.lot_id) | (Lot.public_id == payload.lot_id)).one_or_none()
        if not lot:
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        rows = comparison_for_lot(db, lot)
    else:
        if not payload.material_code or payload.lat is None or payload.lng is None:
            raise HTTPException(status_code=422, detail={"code": "bad_gps"})
        mat = material_by_code(db, payload.material_code)
        rows = candidates(db, payload.lat, payload.lng, mat, payload.weight or 1, None, None)
    return {"ranked": rows, "provider": "score_distance_price_auth_availability_rating"}


@router.post("/predict-price")
def predict_price(payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    mat = material_by_code(db, payload.get("material_code", ""))
    city = payload.get("city") or (user.collector_profile.city if user.collector_profile else "")
    return forecast(db, mat, city)


@router.post("/detect-abnormal-price")
def detect_abnormal(payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    mat = material_by_code(db, payload.get("material_code", ""))
    value = float(payload.get("price_per_kg"))
    hist = [r.price_per_kg for r in db.query(PriceFeed).filter(PriceFeed.material_id == mat.id).all()]
    peers = [o.price_per_kg for o in db.query(RecyclerOffer).filter(RecyclerOffer.material_id == mat.id, RecyclerOffer.active.is_(True)).all()]
    return abnormal(value, hist, peers)


@router.post("/best-sale")
def best_sale(payload: RecommendIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    result = recommend(payload, user, db)
    ranked = [row for row in result["ranked"] if row.get("price_per_kg")]
    ranked.sort(key=lambda row: (-row["net_payout"], row["eta_hours"]))
    return {"best": ranked[0] if ranked else None, "alternatives": ranked[1:4], "provider": "net_payout"}


@router.post("/duplicate-check")
async def duplicate_check(lot_id: str = Form(...), file: UploadFile = File(...), user: User = Depends(require_roles("collector")), db: Session = Depends(get_db)):
    from app.routers.lots import _load, attach_photo

    lot = _load(db, lot_id)
    if lot.collector_id != user.id:
        raise HTTPException(status_code=403, detail={"code": "forbidden"})
    attach_photo(db, lot, await _bytes(file), "collection")
    db.commit()
    return {"duplicate_of": lot.duplicate_of, "score": lot.duplicate_score, "status": lot.duplicate_status, "provider": "phash"}


@router.get("/reliability/{recycler_id}")
def reliability_route(recycler_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data = reliability(db, recycler_id)
    data["provider"] = "rules"
    return data


@router.post("/earnings-predict")
def earnings_predict(user: User = Depends(require_roles("collector")), db: Session = Depends(get_db)):
    from app.models import PaymentLine

    rows = (
        db.query(PaymentLine)
        .join(Transaction, Transaction.id == PaymentLine.transaction_id)
        .filter(Transaction.collector_id == user.id)
        .order_by(PaymentLine.created_at.asc())
        .all()
    )
    buckets: dict[str, float] = {}
    for row in rows:
        key = row.created_at.strftime("%Y-%m")
        buckets[key] = buckets.get(key, 0) + row.amount
    series = [{"month": k, "amount": round(v, 2)} for k, v in buckets.items()]
    if len(series) < 2:
        avg = series[-1]["amount"] if series else 0
        return {"direction": "stable", "forecast": avg, "series": series, "confidence": 0.3, "provider": "average_fallback"}
    amounts = [p["amount"] for p in series]
    try:
        import numpy as np
        from sklearn.linear_model import LinearRegression

        y = np.array(amounts, dtype=float)
        x = np.arange(len(y)).reshape(-1, 1)
        nxt = float(LinearRegression().fit(x, y).predict(np.array([[len(y)]]))[0])
        provider = "sklearn_linear"
    except ImportError:
        n = len(amounts)
        mean_x = (n - 1) / 2
        mean_y = sum(amounts) / n
        den = sum((i - mean_x) ** 2 for i in range(n)) or 1.0
        slope = sum((i - mean_x) * (amount - mean_y) for i, amount in enumerate(amounts)) / den
        nxt = mean_y - slope * mean_x + slope * n
        y = amounts
        provider = "linear_trend"
    direction = "up" if nxt > y[-1] * 1.05 else "down" if nxt < y[-1] * 0.95 else "stable"
    return {"direction": direction, "forecast": round(max(0, nxt), 2), "series": series, "confidence": 0.6, "provider": provider}


class VoiceIn(BaseModel):
    text: str = Field(min_length=1, max_length=400)
    lang: str = "hi"
    lat: float | None = None
    lng: float | None = None


def _say(lang: str, en: str, hi: str, mr: str) -> str:
    return {"hi": hi, "mr": mr}.get(lang, en)


@router.post("/voice")
def voice(payload: VoiceIn, db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)):
    intent = detect_intent(payload.text)
    material_code = detect_material(payload.text)
    provider = "keyword"
    if intent == "unknown":
        guessed = llm_intent(payload.text)
        if guessed:
            intent = guessed.get("intent") or "unknown"
            if guessed.get("material") and guessed["material"] != "null":
                material_code = guessed["material"]
            provider = "llm"
    lang = payload.lang if payload.lang in {"en", "hi", "mr"} else (user.preferred_language if user else "en")
    if intent == "safety" or (intent == "unknown" and safety_answer(payload.text, lang)):
        safety = safety_answer(payload.text, lang) or safety_answer("safety battery crt burn ppe", lang)
        if safety and intent != "unknown":
            return {"intent": "safety", "answer": safety["answer"], "provider": provider, "data": safety}
    if intent == "price":
        code = material_code or "PCB"
        mat = material_by_code(db, code)
        city = user.collector_profile.city if user and user.collector_profile else "Hyderabad"
        quote = estimate_value(db, mat, 1, city)
        answer = _say(
            lang,
            f"{mat.name_en} is {quote['price_per_kg']:.0f} rupees per kilogram in {quote['market']}.",
            f"{mat.name_hi} का भाव {quote['price_per_kg']:.0f} रुपये प्रति किलो है, {quote['market']} में।",
            f"{mat.name_mr} चा भाव {quote['price_per_kg']:.0f} रुपये प्रति किलो आहे, {quote['market']} मध्ये.",
        )
        return {"intent": "price", "answer": answer, "provider": provider, "data": quote, "material": code}
    if intent == "earnings":
        if not user or user.role != "collector":
            answer = _say(lang, "Log in as a collector to hear your earnings.", "कमाई सुनने के लिए कलेक्टर के रूप में लॉग इन करें।", "कमाई ऐकण्यासाठी कलेक्टर म्हणून लॉग इन करा.")
            return {"intent": "earnings", "answer": answer, "provider": provider, "data": {}}
        total = db.query(Transaction).filter(Transaction.collector_id == user.id).all()
        earned = money(sum(t.paid_amount for t in total))
        answer = _say(lang, f"You have received {earned:.0f} rupees.", f"आपको {earned:.0f} रुपये मिले हैं।", f"तुम्हाला {earned:.0f} रुपये मिळाले आहेत.")
        return {"intent": "earnings", "answer": answer, "provider": provider, "data": {"earned": earned}}
    if intent == "nearby":
        materials = user.collector_profile.materials if user and user.collector_profile and user.collector_profile.materials else []
        code = material_code or (materials[0] if materials else "PCB")
        lat = payload.lat if payload.lat is not None else (user.collector_profile.lat if user and user.collector_profile else 17.385)
        lng = payload.lng if payload.lng is not None else (user.collector_profile.lng if user and user.collector_profile else 78.4867)
        rows = candidates(db, lat or 17.385, lng or 78.4867, material_by_code(db, code), 1, 25, None)
        name = rows[0]["business_name"] if rows else ""
        answer = _say(
            lang,
            f"Nearest authorized recycler: {name}." if name else "No authorized recycler found nearby.",
            f"सबसे नज़दीकी अधिकृत रीसाइक्लर: {name}." if name else "पास में अधिकृत रीसाइक्लर नहीं मिला।",
            f"सर्वात जवळचा अधिकृत रिसायकलर: {name}." if name else "जवळ अधिकृत रिसायकलर सापडला नाही.",
        )
        return {"intent": "nearby", "answer": answer, "provider": provider, "data": rows[:3]}
    if intent == "create_lot":
        answer = _say(lang, "Open Digital Lots and add a photo, material and weight.", "डिजिटल लॉट खोलें और फोटो, सामग्री और वजन जोड़ें।", "डिजिटल लॉट उघडा आणि फोटो, साहित्य आणि वजन जोडा.")
        return {"intent": "create_lot", "answer": answer, "provider": provider, "data": {"material": material_code}}
    safety = safety_answer(payload.text, lang)
    if safety:
        return {"intent": "safety", "answer": safety["answer"], "provider": "safety_kb", "data": safety}
    answer = _say(
        lang,
        "I can help with price, safety, earnings, nearby recyclers, or creating a lot.",
        "मैं भाव, सुरक्षा, कमाई, नज़दीकी रीसाइक्लर या नया लॉट बता सकता हूँ।",
        "मी भाव, सुरक्षा, कमाई, जवळचे रिसायकलर किंवा नवीन लॉट सांगू शकतो.",
    )
    return {"intent": "unknown", "answer": answer, "provider": provider}


@router.post("/safety")
def safety(payload: VoiceIn, user: User = Depends(get_current_user)):
    lang = payload.lang if payload.lang in {"en", "hi", "mr"} else "en"
    found = safety_answer(payload.text, lang)
    if not found:
        found = safety_answer("battery crt burn ppe", lang)
        found = {"topic": "overview", "answer": found["answer"] if found else "", "provider": "safety_kb"}
    return found


class AlertIn(BaseModel):
    material_code: str
    direction: str = "above"
    threshold: float | None = None
    change_pct: float | None = None
    city: str = ""


@router.post("/price-alerts")
def create_alert(payload: AlertIn, user: User = Depends(require_roles("collector")), db: Session = Depends(get_db)):
    from app.models import PriceAlertRule

    if payload.direction not in {"above", "below", "change"}:
        raise HTTPException(status_code=422, detail={"code": "bad_status"})
    mat = material_by_code(db, payload.material_code)
    rule = PriceAlertRule(
        collector_id=user.id,
        material_id=mat.id,
        city=payload.city or (user.collector_profile.city if user.collector_profile else ""),
        direction=payload.direction,
        threshold=payload.threshold,
        change_pct=payload.change_pct,
        auto=False,
        active=True,
    )
    db.add(rule)
    db.commit()
    return {"id": rule.id}


@router.get("/price-alerts")
def list_alerts(user: User = Depends(require_roles("collector")), db: Session = Depends(get_db)):
    from app.models import PriceAlertRule

    rows = db.query(PriceAlertRule).filter(PriceAlertRule.collector_id == user.id).all()
    out = []
    for row in rows:
        mat = db.get(Material, row.material_id) if row.material_id else None
        out.append({"id": row.id, "material": mat.code if mat else "", "direction": row.direction, "threshold": row.threshold, "change_pct": row.change_pct, "auto": row.auto, "active": row.active})
    return out
