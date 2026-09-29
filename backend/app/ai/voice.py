import re

import httpx

from app.config import get_settings

MATERIALS = {
    "PCB": ["pcb", "circuit", "सर्किट", "पीसीबी", "pc b"],
    "Cable": ["cable", "wire", "केबल", "वायर", "तार", "वायर"],
    "Battery": ["battery", "बैटरी", "बॅटरी", "batri"],
    "CRT": ["crt", "सीआरटी", "picture tube"],
    "LCD": ["lcd", "एलसीडी", "screen", "स्क्रीन", "monitor"],
    "Plastic": ["plastic", "प्लास्टिक", "प्लॅस्टिक"],
    "Metal": ["metal", "धातु", "लोहा", "लोखंड", "steel", "loha"],
    "Aluminium": ["aluminium", "aluminum", "एल्युमिनियम", "अल्युमिनियम", "aluminium"],
    "Copper": ["copper", "तांबा", "तांबे", "कॉपर", "तांबं", "tamba"],
    "Paper/Cardboard": ["paper", "cardboard", "कागज", "कागद", "कार्डबोर्ड", "raddi", "रद्दी", "paperboard"],
}

INTENTS = {
    "price": ["bhav", "bhaav", "भाव", "price", "rate", "किंमत", "दर", "kitna", "कितना", "किती"],
    "safety": ["safety", "suraksha", "सुरक्षा", "सुरक्षित", "safe", "jalna", "burn", "जलना"],
    "earnings": ["earning", "kamai", "कमाई", "कमाई", "income", "balance", "पैसे", "कमाई", "kamai"],
    "nearby": ["nearby", "paas", "पास", "जवळ", "recycler", "kabadi", "कबाड़ी", "कबाडी"],
    "create_lot": ["create lot", "नया लॉट", "लॉट बना", "लॉट तयार", "new lot", "lot banao", "lot tayaar"],
}


def detect_material(text: str) -> str | None:
    low = text.lower()
    for code, words in MATERIALS.items():
        for word in words:
            if word.lower() in low:
                return code
    return None


def detect_intent(text: str) -> str:
    low = text.lower()
    for intent, words in INTENTS.items():
        for word in words:
            if word.lower() in low:
                return intent
    if re.search(r"\b(lot|लॉट)\b", low) and re.search(r"\b(bana|create|new|तयार|बना)\b", low):
        return "create_lot"
    return "unknown"


def llm_intent(text: str) -> dict | None:
    settings = get_settings()
    if not settings.llm_api_key:
        return None
    prompt = (
        "Classify this scrap-collector utterance. Reply JSON only: "
        '{"intent":"price|safety|earnings|nearby|create_lot|unknown","material":"PCB|Cable|Battery|CRT|LCD|Plastic|Metal|Aluminium|Copper|Paper/Cardboard|null"}. '
        f"Utterance: {text}"
    )
    try:
        response = httpx.post(
            settings.llm_api_url,
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            json={"model": settings.llm_model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 80},
            timeout=20,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        import json

        return json.loads(content[content.find("{") : content.rfind("}") + 1])
    except Exception:
        return None
