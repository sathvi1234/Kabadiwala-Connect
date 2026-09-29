from datetime import datetime

from app.config import get_settings
from app.services.common import haversine_km, now


def collection_flags(lat, lng, captured_at: datetime, has_photo: bool, offline: bool) -> dict:
    settings = get_settings()
    delta = abs((now() - captured_at).total_seconds())
    time_ok = delta <= settings.timestamp_tolerance_seconds or offline
    return {
        "gps_present": lat is not None and lng is not None,
        "photo_present": has_photo,
        "time_ok": time_ok,
        "time_delta_seconds": int(delta),
        "offline_capture": offline,
        "distance_suspicious": False,
        "distance_km": None,
    }


def handover_flags(lot_lat, lot_lng, hand_lat, hand_lng, captured_at: datetime, has_photo: bool, declared: float, verified: float | None) -> dict:
    settings = get_settings()
    delta = abs((now() - captured_at).total_seconds())
    distance = None
    suspicious = False
    if None not in (lot_lat, lot_lng, hand_lat, hand_lng):
        distance = round(haversine_km(lot_lat, lot_lng, hand_lat, hand_lng), 3)
        suspicious = distance > settings.handover_distance_flag_km
    diff = None if verified is None else round(verified - declared, 3)
    weight_flag = diff is not None and declared and abs(diff) / declared > 0.1
    return {
        "gps_present": hand_lat is not None and hand_lng is not None,
        "photo_present": has_photo,
        "time_ok": delta <= settings.timestamp_tolerance_seconds,
        "time_delta_seconds": int(delta),
        "distance_suspicious": suspicious,
        "distance_km": distance,
        "weight_difference_kg": diff,
        "weight_mismatch": bool(weight_flag),
    }
