import io
from collections import Counter

from PIL import Image


CATEGORIES = ["PCB", "Cable", "Battery", "CRT", "LCD", "Plastic", "Metal", "Paper/Cardboard"]


def _stats(image: Image.Image):
    small = image.convert("RGB").resize((32, 32))
    pixels = list(small.getdata())
    n = len(pixels)
    avg = [sum(p[i] for p in pixels) / n for i in range(3)]
    lum = [(0.299 * r + 0.587 * g + 0.114 * b) for r, g, b in pixels]
    mean = sum(lum) / n
    var = sum((v - mean) ** 2 for v in lum) / n
    green = avg[1] - max(avg[0], avg[2])
    return avg, mean, var ** 0.5, green


def classify_color(avg, mean, green) -> tuple[str, float]:
    r, g, b = avg
    if green > 12 and g > 70:
        return "PCB", min(0.62, 0.4 + green / 80)
    if b > r + 15 and b > g + 10 and mean > 90:
        return "LCD", 0.48
    if r > 140 and g > 90 and b < 80 and r > g:
        return "Copper", 0.46
    if abs(r - g) < 18 and abs(g - b) < 18 and mean > 170:
        return "Paper/Cardboard", 0.5
    if r > 90 and g > 90 and b < 80 and abs(r - g) < 30:
        return "Aluminium", 0.42
    if mean < 55:
        return "Battery", 0.45
    if mean < 90 and max(r, g, b) - min(r, g, b) < 30:
        return "Metal", 0.44
    if g > r and b < g:
        return "Plastic", 0.4
    if r > 100 and g > 70 and b > 70:
        return "Cable", 0.38
    return "Plastic", 0.35


def identify_image(data: bytes) -> dict:
    image = Image.open(io.BytesIO(data))
    avg, mean, std, green = _stats(image)
    material, confidence = classify_color(avg, mean, green)
    if material == "Copper":
        material = "Cable"
    alternatives = []
    for code in CATEGORIES:
        if code != material:
            alternatives.append({"material": code, "confidence": round(max(0.05, confidence - 0.25), 2)})
    alternatives = sorted(alternatives, key=lambda item: -item["confidence"])[:3]
    return {
        "material": material,
        "confidence": round(confidence, 2),
        "alternatives": alternatives,
        "provider": "heuristic",
    }


def condition_image(data: bytes) -> dict:
    image = Image.open(io.BytesIO(data))
    avg, mean, std, _green = _stats(image)
    if std > 55 and mean < 90:
        label, note = "damaged", "High contrast and dark areas suggest breakage or corrosion."
    elif std > 40:
        label, note = "mixed", "Uneven colour suggests more than one condition or material."
    elif mean > 150 and std < 30:
        label, note = "good", "Even, bright surface."
    else:
        label, note = "used", "Typical used scrap surface."
    return {"condition": label, "note": note, "provider": "heuristic"}


def mixed_scrap(data: bytes) -> dict:
    image = Image.open(io.BytesIO(data)).convert("RGB")
    w, h = image.size
    counts: Counter[str] = Counter()
    for gy in range(4):
        for gx in range(4):
            crop = image.crop((gx * w // 4, gy * h // 4, (gx + 1) * w // 4, (gy + 1) * h // 4))
            avg, mean, _std, green = _stats(crop)
            label, _conf = classify_color(avg, mean, green)
            if label == "Copper":
                label = "Cable"
            if label == "Aluminium":
                label = "Metal"
            counts[label] += 1
    total = sum(counts.values()) or 1
    items = [
        {"material": name, "share": round(count / total, 2)}
        for name, count in counts.most_common()
        if count / total >= 0.08
    ]
    return {"materials": items, "provider": "heuristic"}
