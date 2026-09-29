from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db

bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def create_token(user_id: str, role: str) -> str:
    settings = get_settings()
    payload = {
        "sub": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_exp_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail={"code": "invalid_token"}) from exc


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
):
    from app.models import User

    if creds is None:
        raise HTTPException(status_code=401, detail={"code": "auth_required"})
    payload = decode_token(creds.credentials)
    user = db.get(User, payload.get("sub"))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail={"code": "auth_required"})
    return user


def get_optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
):
    from app.models import User

    if creds is None:
        return None
    try:
        payload = decode_token(creds.credentials)
    except HTTPException:
        return None
    user = db.get(User, payload.get("sub"))
    if not user or not user.is_active:
        return None
    return user


def deny_if_demo(user) -> None:
    if getattr(user, "is_demo", False):
        raise HTTPException(status_code=403, detail={"code": "demo_locked"})


def require_roles(*roles: str):
    def _dep(user=Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(status_code=403, detail={"code": "forbidden"})
        return user

    return _dep
