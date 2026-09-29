import time
from collections import defaultdict

from fastapi import HTTPException, Request

_hits: dict[str, list[float]] = defaultdict(list)


def limit(request: Request, bucket: str, max_hits: int, window: int = 60):
    ip = request.client.host if request.client else "local"
    key = f"{bucket}:{ip}"
    now = time.time()
    recent = [t for t in _hits[key] if now - t < window]
    if len(recent) >= max_hits:
        raise HTTPException(status_code=429, detail={"code": "rate_limited"})
    recent.append(now)
    _hits[key] = recent
