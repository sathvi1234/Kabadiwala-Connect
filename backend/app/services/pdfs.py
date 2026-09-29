import io
from datetime import datetime

import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.storage import absolute_path, upload_root


def _qr_image(text: str):
    image = qrcode.make(text)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    buf.seek(0)
    path = upload_root() / "tmp"
    path.mkdir(parents=True, exist_ok=True)
    file_path = path / "qr.png"
    file_path.write_bytes(buf.getvalue())
    return str(file_path)


def build_receipt_pdf(rel_path: str, receipt_number: str, lines: list[tuple[str, str]], verify_url: str) -> str:
    dest = absolute_path(rel_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(dest), pagesize=A4)
    c.setTitle(receipt_number)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(20 * mm, 270 * mm, "Kabadiwala Connect")
    c.setFont("Helvetica", 12)
    c.drawString(20 * mm, 262 * mm, "Digital payment receipt")
    y = 248 * mm
    for label, value in lines:
        c.setFont("Helvetica-Bold", 11)
        c.drawString(20 * mm, y, label)
        c.setFont("Helvetica", 11)
        c.drawString(70 * mm, y, str(value))
        y -= 8 * mm
    c.drawImage(_qr_image(verify_url), 20 * mm, y - 45 * mm, 35 * mm, 35 * mm, preserveAspectRatio=True, mask="auto")
    c.setFont("Helvetica", 9)
    c.drawString(60 * mm, y - 20 * mm, verify_url)
    c.save()
    return rel_path


def build_certificate_pdf(rel_path: str, lot_public_id: str, lines: list[tuple[str, str]], verify_url: str) -> str:
    dest = absolute_path(rel_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(dest), pagesize=A4)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(20 * mm, 270 * mm, "Digital handover certificate")
    c.setFont("Helvetica", 11)
    c.drawString(20 * mm, 260 * mm, lot_public_id)
    y = 246 * mm
    for label, value in lines:
        c.drawString(20 * mm, y, f"{label}: {value}")
        y -= 8 * mm
    c.drawImage(_qr_image(verify_url), 20 * mm, 40 * mm, 40 * mm, 40 * mm, preserveAspectRatio=True, mask="auto")
    c.setFont("Helvetica", 9)
    c.drawString(65 * mm, 55 * mm, verify_url)
    c.drawString(20 * mm, 30 * mm, f"Generated {datetime.utcnow().isoformat(timespec='seconds')}Z")
    c.save()
    return rel_path
