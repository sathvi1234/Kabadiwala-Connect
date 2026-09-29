import io
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image

from app.config import get_settings

IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
DOC_TYPES = {**IMAGE_TYPES, "application/pdf": ".pdf"}


def upload_root() -> Path:
    settings = get_settings()
    path = Path(settings.upload_dir)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[1] / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def _sniff(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"\x89PNG"):
        return ".png"
    if data.startswith(b"RIFF") and b"WEBP" in data[:16]:
        return ".webp"
    if data.startswith(b"%PDF"):
        return ".pdf"
    return None


async def save_upload(file: UploadFile, folder: str, *, images_only: bool = False, recompress: bool = False) -> str:
    settings = get_settings()
    data = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail={"code": "file_too_large"})
    if not data:
        raise HTTPException(status_code=422, detail={"code": "empty_file"})
    ext = _sniff(data)
    allowed = {".jpg", ".png", ".webp"} if images_only else {".jpg", ".png", ".webp", ".pdf"}
    if ext not in allowed:
        raise HTTPException(status_code=422, detail={"code": "bad_file_type"})
    if recompress and ext != ".pdf":
        data, ext = recompress_image(data, settings.max_image_kb * 1024)
    name = f"{uuid.uuid4().hex}{ext}"
    dest_dir = upload_root() / folder
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / name).write_bytes(data)
    return f"{folder}/{name}"


def recompress_image(data: bytes, max_bytes: int) -> tuple[bytes, str]:
    image = Image.open(io.BytesIO(data)).convert("RGB")
    quality = 70
    out = data
    for _ in range(6):
        buf = io.BytesIO()
        image.save(buf, format="WEBP", quality=quality, method=4)
        out = buf.getvalue()
        if len(out) <= max_bytes or quality <= 30:
            break
        quality -= 10
        image = image.resize((max(1, int(image.width * 0.85)), max(1, int(image.height * 0.85))))
    return out, ".webp"


def absolute_path(rel: str) -> Path:
    return upload_root() / rel
