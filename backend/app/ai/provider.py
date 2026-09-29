import base64

import httpx

from app.ai.vision import condition_image, identify_image, mixed_scrap
from app.config import get_settings

ALLOWED = {"PCB", "Cable", "Battery", "CRT", "LCD", "Plastic", "Metal", "Paper/Cardboard", "Aluminium", "Copper"}


def _vision_call(data: bytes, prompt: str) -> str | None:
    settings = get_settings()
    if not settings.vision_api_key:
        return None
    b64 = base64.b64encode(data).decode()
    payload = {
        "model": settings.vision_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/webp;base64,{b64}"}},
                ],
            }
        ],
        "max_tokens": 200,
    }
    try:
        response = httpx.post(
            settings.vision_api_url,
            headers={"Authorization": f"Bearer {settings.vision_api_key}"},
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception:
        return None


def identify(data: bytes) -> dict:
    text = _vision_call(
        data,
        "Reply with only one scrap category from: PCB, Cable, Battery, CRT, LCD, Plastic, Metal, Paper/Cardboard. Then a confidence 0-1. Example: PCB 0.91",
    )
    if text:
        parts = text.replace(",", " ").split()
        material = next((p for p in parts if p in ALLOWED or p.upper() in ALLOWED), None)
        if material:
            material = material if material in ALLOWED else material.upper()
            conf = 0.7
            for part in parts:
                try:
                    conf = float(part)
                except ValueError:
                    continue
            return {"material": material, "confidence": conf, "alternatives": [], "provider": "vision_api"}
    return identify_image(data)


def condition(data: bytes) -> dict:
    text = _vision_call(data, "Reply with only one of: good, used, damaged, mixed, then a short note.")
    if text:
        lower = text.lower()
        for label in ("good", "used", "damaged", "mixed"):
            if label in lower:
                return {"condition": label, "note": text.strip(), "provider": "vision_api"}
    return condition_image(data)


def mixed(data: bytes) -> dict:
    return mixed_scrap(data)
