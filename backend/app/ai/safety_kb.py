SAFETY = [
    {
        "id": "battery",
        "keywords": ["battery", "बैटरी", "बॅटरी", "batri", "cell"],
        "en": "Do not puncture, crush, or burn batteries. Keep damaged batteries separate and dry, and hand them only to an authorized recycler.",
        "hi": "बैटरी को न छेदे, न कुचलें और न जलाएँ। खराब बैटरी को अलग और सूखा रखें और केवल अधिकृत रीसाइक्लर को दें।",
        "mr": "बॅटरी टोचू नका, चिरडू नका आणि जाळू नका. खराब बॅटरी वेगळी व कोरडी ठेवा आणि फक्त अधिकृत रिसायकलरला द्या.",
    },
    {
        "id": "crt",
        "keywords": ["crt", "lcd", "screen", "सीआरटी", "एलसीडी", "स्क्रीन", "monitor", "tube"],
        "en": "Do not break CRT or LCD screens. Wear gloves, carry the unit intact, and send it to an authorized recycler.",
        "hi": "CRT या LCD स्क्रीन न तोड़ें। दस्ताने पहनें, यूनिट को साबुत ले जाएँ और अधिकृत रीसाइक्लर को दें।",
        "mr": "CRT किंवा LCD स्क्रीन फोडू नका. हातमोजे घाला, युनिट पूर्ण ठेवा आणि अधिकृत रिसायकलरकडे द्या.",
    },
    {
        "id": "burn",
        "keywords": ["burn", "jalana", "जल", "जाळ", "fire", "आग", "cable burn", "plastic burn"],
        "en": "Do not burn cables, plastic, or e-waste. Burning releases toxic smoke. Use a formal recycler instead.",
        "hi": "केबल, प्लास्टिक या ई-कचरा न जलाएँ। जलाने से जहरीला धुआँ निकलता है। औपचारिक रीसाइक्लर को दें।",
        "mr": "केबल, प्लॅस्टिक किंवा ई-कचरा जाळू नका. जाळल्याने विषारी धूर निघतो. अधिकृत रिसायकलरकडे द्या.",
    },
    {
        "id": "ppe",
        "keywords": ["ppe", "glove", "दस्ताने", "हातमोजे", "mask", "safety gear", "sharp", "तेज", "धार"],
        "en": "Wear gloves, closed shoes, and eye protection. Watch for sharp edges and do not handle broken glass with bare hands.",
        "hi": "दस्ताने, बंद जूते और आँखों की सुरक्षा पहनें। तेज किनारों से बचें और टूटा काँच नंगे हाथ से न छुएँ।",
        "mr": "हातमोजे, बंद बूट आणि डोळ्यांचे संरक्षण वापरा. धारदार कडा टाळा आणि तुटलेला काच उघड्या हाताने हाताळू नका.",
    },
]


def answer(text: str, lang: str) -> dict | None:
    low = text.lower()
    for item in SAFETY:
        if any(word.lower() in low for word in item["keywords"]):
            key = lang if lang in {"en", "hi", "mr"} else "en"
            return {"topic": item["id"], "answer": item[key], "provider": "safety_kb"}
    return None
