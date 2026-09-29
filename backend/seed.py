"""Idempotent demo data for Kabadiwala Connect."""

import math
import os
import random
from datetime import date, datetime, timedelta

from app.database import SessionLocal, engine
from app.database import Base
from app.models import (
    Badge,
    CollectorProfile,
    CommunityEvent,
    Dispute,
    Handover,
    LedgerEntry,
    Lot,
    LotEvent,
    Material,
    PaymentLine,
    Pickup,
    PriceFeed,
    RatingFeedback,
    RecyclerOffer,
    RecyclerProfile,
    Referral,
    Transaction,
    Testimonial,
    Tutorial,
    User,
    utcnow,
)
from app.security import hash_password
from app.services.common import money
import app.models  # noqa: F401

MATERIALS = [
    ("PCB", "PCB", "पीसीबी", "पीसीबी", 2.5, "Illustrative WEEE factor, order of magnitude from UNU Global E-waste Monitor discussions of formal recycling benefits"),
    ("Cable", "Cable", "केबल", "केबल", 2.0, "Copper-content share of ICA recycled-copper energy savings, scaled for mixed cable"),
    ("Battery", "Battery", "बैटरी", "बॅटरी", 1.2, "Lead-acid recycling literature (International Lead Association), illustrative kg CO2e avoided per kg"),
    ("CRT", "CRT", "सीआरटी", "सीआरटी", 0.8, "Illustrative WEEE handling factor for intact CRT glass and metal"),
    ("LCD", "LCD", "एलसीडी", "एलसीडी", 1.5, "Illustrative flat-panel WEEE factor"),
    ("Plastic", "Plastic", "प्लास्टिक", "प्लॅस्टिक", 1.5, "EPA WARM mixed plastics recycling versus landfill, approximate kg CO2e per kg"),
    ("Metal", "Metal", "धातु", "धातू", 1.8, "EPA WARM steel cans / mixed metals, approximate kg CO2e per kg"),
    ("Aluminium", "Aluminium", "एल्युमिनियम", "अ‍ॅल्युमिनियम", 9.0, "International Aluminium Institute: primary versus recycled aluminium, avoided about 9 kg CO2e/kg"),
    ("Copper", "Copper", "तांबा", "तांबे", 4.0, "International Copper Association: recycled copper saves most of the primary production energy, about 4 kg CO2e/kg"),
    ("Paper/Cardboard", "Paper/Cardboard", "कागज/कार्डबोर्ड", "कागद/कार्डबोर्ड", 0.9, "EPA WARM corrugated containers recycling versus landfill, approximate kg CO2e per kg"),
]

BASE_PRICES = {
    "PCB": 420,
    "Cable": 85,
    "Battery": 90,
    "CRT": 18,
    "LCD": 42,
    "Plastic": 18,
    "Metal": 36,
    "Aluminium": 140,
    "Copper": 720,
    "Paper/Cardboard": 12,
}

TUTORIALS = {
    "lots": {
        "en": ("Create a lot", "Take a photo of the scrap, choose the material, enter the weight, and save the lot. A QR code is created for handover."),
        "hi": ("लॉट बनाएँ", "कचरे की फोटो लें, सामग्री चुनें, वजन लिखें और लॉट सहेजें। हैंडओवर के लिए क्यूआर कोड बनेगा।"),
        "mr": ("लॉट तयार करा", "कचऱ्याचा फोटो घ्या, साहित्य निवडा, वजन लिहा आणि लॉट जतन करा. हस्तांतरणासाठी क्यूआर कोड तयार होईल."),
    },
    "prices": {
        "en": ("Check prices", "Open the price board to see today's rate, the source, and the date. Use the chart for 7, 30, 90 days or one year."),
        "hi": ("भाव देखें", "आज का भाव, स्रोत और तारीख देखने के लिए प्राइस बोर्ड खोलें। सात, तीस, नब्बे दिन या एक साल का चार्ट देखें।"),
        "mr": ("भाव पाहा", "आजचा भाव, स्रोत आणि तारीख पाहण्यासाठी किंमत बोर्ड उघडा. सात, तीस, नव्वद दिवस किंवा एक वर्षाचा तक्ता पाहा."),
    },
    "safety": {
        "en": ("Stay safe", "Do not burn e-waste or break batteries and screens. Wear gloves and use the emergency button if you need help."),
        "hi": ("सुरक्षित रहें", "ई-कचरा न जलाएँ और बैटरी या स्क्रीन न तोड़ें। दस्ताने पहनें और मदद के लिए इमरजेंसी बटन दबाएँ।"),
        "mr": ("सुरक्षित राहा", "ई-कचरा जाळू नका आणि बॅटरी किंवा स्क्रीन फोडू नका. हातमोजे घाला आणि मदतीसाठी आपत्कालीन बटण दाबा."),
    },
    "handover": {
        "en": ("Handover", "When the recycler arrives, both of you confirm the weight, photo and location. Then record cash, UPI or bank payment."),
        "hi": ("हैंडओवर", "रीसाइक्लर के आने पर दोनों वजन, फोटो और जगह की पुष्टि करें। फिर नकद, यूपीआई या बैंक भुगतान दर्ज करें।"),
        "mr": ("हस्तांतरण", "रिसायकलर आल्यावर दोघे वजन, फोटो आणि ठिकाण निश्चित करा. नंतर रोख, यूपीआई किंवा बँक पेमेंट नोंदवा."),
    },
    "offline": {
        "en": ("Offline use", "You can create a lot without internet. It stays pending and syncs when you are online. Press Sync now if you want to send it immediately."),
        "hi": ("ऑफलाइन उपयोग", "बिना इंटरनेट के भी लॉट बना सकते हैं। वह लंबित रहेगा और ऑनलाइन होते ही सिंक होगा। तुरंत भेजने के लिए सिंक नाउ दबाएँ।"),
        "mr": ("ऑफलाइन वापर", "इंटरनेटशिवाय लॉट तयार करता येतो. तो प्रलंबित राहतो आणि ऑनलाइन होताच सिंक होतो. लगेच पाठवण्यासाठी सिंक नाउ दाबा."),
    },
}


def _user(phone, name, role, lang, password="Demo@123"):
    return User(
        phone=phone,
        name=name,
        role=role,
        preferred_language=lang,
        password_hash=hash_password(password),
        referral_code=phone[-6:],
        is_active=True,
        is_demo=True,
        created_at=utcnow() - timedelta(days=40),
    )


QUOTES = (
    ("Lakshmi Bai", "collector", "Hyderabad", "I check the board before I sell cable. The lot QR means the yard cannot change the weight later.", "केबल बेचने से पहले मैं भाव देखती हूँ। लॉट का क्यूआर होने से वजन बाद में नहीं बदलता।", "केबल विकण्यापूर्वी मी भाव बघते. लॉटच्या क्यूआरमुळे वजन नंतर बदलत नाही."),
    ("Anita Rao", "recycler", "Hyderabad", "Pickup slots and the handover photo cut down arguments at the gate.", "पिकअप समय और हैंडओवर फोटो से गेट पर बहस कम हो गई है।", "पिकअप वेळ आणि हँडओवर फोटोमुळे गेटवरील वाद कमी झाले."),
    ("Farooq", "collector", "Pune", "Hindi voice tells me the battery price when my hands are full.", "हाथ भरे हों तब हिन्दी आवाज़ बैटरी का भाव बता देती है।", "हात भरलेले असताना हिंदी आवाज बॅटरीचा भाव सांगते."),
)


def seed_extras() -> None:
    from app.database import ensure_columns
    from app.models import Testimonial

    ensure_columns()
    Base.metadata.create_all(engine)
    db = SessionLocal()
    phones = {
        "9999999999": "admin@kabadiwala.local",
        "9000000001": "ramesh@kabadiwala.local",
        "9000000002": "savita@kabadiwala.local",
        "9000000003": "imran@kabadiwala.local",
        "9000000011": "greencycle@kabadiwala.local",
        "9000000012": "ecoloop@kabadiwala.local",
        "9000000013": "metro@kabadiwala.local",
        "9000000014": "pending@kabadiwala.local",
    }
    for phone, email in phones.items():
        account = db.query(User).filter(User.phone == phone).one_or_none()
        if account:
            account.is_demo = True
            if not account.email:
                account.email = email
    if db.query(Testimonial).count() == 0:
        for name, role, city, en, hi, mr in QUOTES:
            db.add(Testimonial(name=name, role=role, city=city, quote_en=en, quote_hi=hi, quote_mr=mr, created_at=utcnow()))
    db.commit()
    db.close()


def seed():
    from app.database import ensure_columns

    ensure_columns()
    Base.metadata.create_all(engine)
    db = SessionLocal()
    if db.query(User).filter(User.phone == "9999999999").first():
        db.close()
        seed_extras()
        print("Seed already present")
        return
    rng = random.Random(26229)
    materials = {}
    for code, en, hi, mr, factor, source in MATERIALS:
        row = Material(code=code, name_en=en, name_hi=hi, name_mr=mr, co2_factor=factor, factor_source=source)
        db.add(row)
        materials[code] = row
    db.flush()

    today = date.today()
    history_days = int(os.environ.get("SEED_HISTORY_DAYS", "365"))
    for offset in range(history_days, -1, -1):
        recorded = today - timedelta(days=offset)
        seasonal = 1 + 0.05 * math.sin(2 * math.pi * recorded.timetuple().tm_yday / 365)
        for code, base in BASE_PRICES.items():
            hy = round(base * seasonal * (1 + rng.uniform(-0.015, 0.015)), 2)
            pu = round(hy * 0.98, 2)
            db.add(PriceFeed(material_id=materials[code].id, price_per_kg=hy, source="Local yard board", market="Hyderabad", recorded_on=recorded, created_at=datetime.combine(recorded, datetime.min.time())))
            db.add(PriceFeed(material_id=materials[code].id, price_per_kg=pu, source="Local yard board", market="Pune", recorded_on=recorded, created_at=datetime.combine(recorded, datetime.min.time())))

    for code, threshold, name, desc in (
        ("bronze", 50, "Bronze", "50 verified handovers"),
        ("silver", 100, "Silver", "100 verified handovers"),
        ("gold", 250, "Gold", "250 verified handovers"),
    ):
        db.add(Badge(code=code, name=name, description=desc, threshold=threshold))

    admin = _user("9999999999", "Admin", "admin", "en")
    ramesh = _user("9000000001", "Ramesh Kumar", "collector", "hi")
    savita = _user("9000000002", "Savita Pawar", "collector", "mr")
    imran = _user("9000000003", "Imran Shaikh", "collector", "hi")
    imran.referred_by_code = ramesh.referral_code
    g_user = _user("9000000011", "Anita Rao", "recycler", "en")
    e_user = _user("9000000012", "Farhan Ali", "recycler", "hi")
    m_user = _user("9000000013", "Metro Desk", "recycler", "mr")
    p_user = _user("9000000014", "Pending Yard", "recycler", "en")
    db.add_all([admin, ramesh, savita, imran, g_user, e_user, m_user, p_user])
    db.flush()
    db.add(Referral(referrer_id=ramesh.id, code=ramesh.referral_code, referred_user_id=imran.id, rewarded=False, created_at=utcnow()))

    db.add(CollectorProfile(user_id=ramesh.id, area="Secunderabad", city="Hyderabad", lat=17.439, lng=78.498, materials=["PCB", "Copper", "Cable"], emergency_contact="9000000099"))
    db.add(CollectorProfile(user_id=savita.id, area="Kothrud", city="Pune", lat=18.507, lng=73.807, materials=["Plastic", "Paper/Cardboard", "Metal"], emergency_contact="9000000088"))
    db.add(CollectorProfile(user_id=imran.id, area="Charminar", city="Hyderabad", lat=17.361, lng=78.474, materials=["Battery", "Aluminium"], emergency_contact="9000000077"))

    def recycler(user, business, licence, address, city, lat, lng, mats, status, availability, slot, rating=4.6, count=12):
        db.add(
            RecyclerProfile(
                user_id=user.id,
                business_name=business,
                licence_number=licence,
                address=address,
                city=city,
                lat=lat,
                lng=lng,
                materials=mats,
                working_hours={"mon": "09:00-18:00", "tue": "09:00-18:00", "wed": "09:00-18:00", "thu": "09:00-18:00", "fri": "09:00-18:00", "sat": "09:00-14:00"},
                status=status,
                availability=availability,
                next_slot=slot,
                rating_avg=rating,
                rating_count=count,
                reliability_score=90 if status == "approved" else 0,
            )
        )

    recycler(g_user, "GreenCycle Recycling", "TG-EW-1042", "Balanagar Industrial Area", "Hyderabad", 17.45, 78.45, ["PCB", "Cable", "Battery", "CRT", "LCD", "Copper"], "approved", "available", "16:30", 4.8, 28)
    recycler(e_user, "EcoLoop Recyclers", "TG-EW-1188", "Kukatpally", "Hyderabad", 17.494, 78.399, ["Metal", "Aluminium", "Copper", "PCB", "Plastic"], "approved", "available", "17:00", 4.5, 19)
    recycler(m_user, "Metro Scrap Hub", "MH-EW-2210", "Bhosari", "Pune", 18.62, 73.84, ["Metal", "Plastic", "Paper/Cardboard", "Aluminium"], "approved", "busy", "Tomorrow 10:00", 4.2, 11)
    recycler(p_user, "Pending Scrap Co", "TG-PENDING", "Uppal", "Hyderabad", 17.401, 78.559, ["Plastic", "Paper/Cardboard"], "pending", "offline", None, 0, 0)
    db.flush()

    for user, codes in (
        (g_user, {"PCB": 410, "Cable": 80, "Battery": 95, "Copper": 700, "CRT": 16, "LCD": 40}),
        (e_user, {"PCB": 395, "Metal": 34, "Aluminium": 138, "Copper": 690, "Plastic": 16}),
        (m_user, {"Metal": 32, "Plastic": 15, "Paper/Cardboard": 11, "Aluminium": 130}),
    ):
        for code, price in codes.items():
            db.add(RecyclerOffer(recycler_id=user.id, material_id=materials[code].id, price_per_kg=price, active=True, created_at=utcnow()))

    def add_lot(collector, code, kg, status, city, lat, lng, days_ago, flags):
        recorded = date.today() - timedelta(days=days_ago)
        price = BASE_PRICES[code]
        lot = Lot(
            public_id=f"LOT-{recorded.strftime('%Y%m%d')}-{code[:3].upper()}{days_ago:02d}",
            collector_id=collector.id,
            material_id=materials[code].id,
            weight_kg=kg,
            input_weight=kg,
            input_unit="kg",
            lat=lat,
            lng=lng,
            city=city,
            captured_at=datetime.combine(recorded, datetime.min.time()) + timedelta(hours=10),
            status=status,
            estimated_value=money(kg * price),
            price_per_kg=price,
            price_source="Local yard board",
            price_date=recorded.isoformat(),
            price_market=city,
            flags=flags,
            created_at=datetime.combine(recorded, datetime.min.time()) + timedelta(hours=10),
            updated_at=utcnow(),
        )
        db.add(lot)
        db.flush()
        db.add(LotEvent(lot_id=lot.id, event_type="collection", actor_id=collector.id, actor_role="collector", note=f"{code} {kg} kg", lat=lat, lng=lng, created_at=lot.captured_at))
        return lot

    ok_flags = {"gps_present": True, "photo_present": False, "time_ok": True, "distance_suspicious": False}
    lot_paid = add_lot(ramesh, "PCB", 7, "completed", "Hyderabad", 17.44, 78.49, 12, ok_flags)
    lot_hand = add_lot(savita, "Aluminium", 12, "handed_over", "Pune", 18.51, 73.81, 2, ok_flags)
    lot_pick = add_lot(ramesh, "Cable", 18, "pickup_scheduled", "Hyderabad", 17.44, 78.5, 0, ok_flags)
    add_lot(imran, "Battery", 9, "open", "Hyderabad", 17.36, 78.47, 1, {"gps_present": True, "photo_present": False, "time_ok": True, "distance_suspicious": False})
    lot_disp = add_lot(ramesh, "Copper", 4, "disputed", "Hyderabad", 17.43, 78.48, 6, {**ok_flags, "weight_mismatch": True})

    def chain(lot, recycler_user, when, pickup_status="completed"):
        db.add(LotEvent(lot_id=lot.id, event_type="pickup_scheduled", actor_id=lot.collector_id, actor_role="collector", note="scheduled", created_at=lot.created_at + timedelta(hours=1)))
        db.add(Pickup(lot_id=lot.id, recycler_id=recycler_user.id, collector_id=lot.collector_id, scheduled_at=when, status=pickup_status, created_at=lot.created_at + timedelta(hours=1)))
        db.add(LotEvent(lot_id=lot.id, event_type="pickup_accepted", actor_id=recycler_user.id, actor_role="recycler", note="accepted", created_at=when))

    chain(lot_paid, g_user, lot_paid.created_at + timedelta(hours=3))
    db.add(Handover(lot_id=lot_paid.id, collector_confirmed_at=lot_paid.created_at + timedelta(hours=4), recycler_confirmed_at=lot_paid.created_at + timedelta(hours=4, minutes=5), lat=17.45, lng=78.45, weight_verified_kg=7, weight_difference_kg=0, flags=ok_flags, created_at=lot_paid.created_at + timedelta(hours=4)))
    db.add(LotEvent(lot_id=lot_paid.id, event_type="handover", actor_id=g_user.id, actor_role="recycler", note="confirmed", created_at=lot_paid.created_at + timedelta(hours=4)))
    db.add(LotEvent(lot_id=lot_paid.id, event_type="processing", actor_id=g_user.id, actor_role="recycler", note="complete", created_at=lot_paid.created_at + timedelta(days=1)))
    tx1 = Transaction(public_id="TX-9001", lot_id=lot_paid.id, collector_id=ramesh.id, recycler_id=g_user.id, amount=2940, paid_amount=2940, mode="upi", status="paid", created_at=lot_paid.created_at + timedelta(hours=5))
    db.add(tx1)
    db.flush()
    db.add(PaymentLine(transaction_id=tx1.id, amount=2940, mode="upi", reference="UPI123456", created_at=tx1.created_at))
    db.add(LedgerEntry(collector_id=ramesh.id, transaction_id=tx1.id, entry_type="credit", amount=2940, balance_after=2940, note="UPI for TX-9001", created_at=tx1.created_at))
    db.add(RatingFeedback(lot_id=lot_paid.id, collector_id=ramesh.id, recycler_id=g_user.id, stars=5, comment="On time and correct weight", created_at=tx1.created_at))

    chain(lot_hand, m_user, lot_hand.created_at + timedelta(hours=2), "accepted")
    db.add(Handover(lot_id=lot_hand.id, collector_confirmed_at=lot_hand.created_at + timedelta(hours=3), recycler_confirmed_at=lot_hand.created_at + timedelta(hours=3, minutes=10), lat=18.52, lng=73.85, weight_verified_kg=12, weight_difference_kg=0, flags=ok_flags, created_at=lot_hand.created_at))
    db.add(LotEvent(lot_id=lot_hand.id, event_type="handover", actor_role="recycler", actor_id=m_user.id, note="confirmed", created_at=lot_hand.created_at + timedelta(hours=3)))
    tx2 = Transaction(public_id="TX-9002", lot_id=lot_hand.id, collector_id=savita.id, recycler_id=m_user.id, amount=1680, paid_amount=500, mode="cash", status="partial", created_at=lot_hand.created_at + timedelta(hours=4))
    db.add(tx2)
    db.flush()
    db.add(PaymentLine(transaction_id=tx2.id, amount=500, mode="cash", reference="", created_at=tx2.created_at))
    db.add(LedgerEntry(collector_id=savita.id, transaction_id=tx2.id, entry_type="credit", amount=500, balance_after=500, note="Cash partial TX-9002", created_at=tx2.created_at))

    chain(lot_pick, g_user, datetime.now().replace(hour=16, minute=30, second=0, microsecond=0), "accepted")

    chain(lot_disp, e_user, lot_disp.created_at + timedelta(hours=2), "accepted")
    db.add(Handover(lot_id=lot_disp.id, collector_confirmed_at=lot_disp.created_at + timedelta(hours=3), recycler_confirmed_at=lot_disp.created_at + timedelta(hours=3, minutes=20), lat=17.49, lng=78.40, weight_verified_kg=3.2, weight_difference_kg=-0.8, flags={**ok_flags, "weight_mismatch": True, "weight_difference_kg": -0.8}, created_at=lot_disp.created_at))
    dispute = Dispute(lot_id=lot_disp.id, raised_by=ramesh.id, against_user=e_user.id, reason="Verified weight is lower than the collected weight.", status="open", created_at=lot_disp.created_at + timedelta(hours=5), updated_at=utcnow())
    db.add(dispute)

    db.add(CommunityEvent(title="Community e-waste drive", city="Hyderabad", lat=17.406, lng=78.477, starts_at=datetime.now() + timedelta(days=7), description="Drop-off at the community hall. No personal collector data is shown.", created_at=utcnow()))
    db.add(CommunityEvent(title="Paper collection drive", city="Pune", lat=18.52, lng=73.856, starts_at=datetime.now() + timedelta(days=12), description="Paper and cardboard only.", created_at=utcnow()))

    for feature, pack in TUTORIALS.items():
        for lang, (title, script) in pack.items():
            db.add(Tutorial(feature_key=feature, lang=lang, title=title, script=script, created_at=utcnow()))

    for name, role, city, en, hi, mr in QUOTES:
        db.add(Testimonial(name=name, role=role, city=city, quote_en=en, quote_hi=hi, quote_mr=mr, created_at=utcnow()))

    db.commit()
    db.close()
    print("Seeded Kabadiwala Connect")


if __name__ == "__main__":
    seed()
