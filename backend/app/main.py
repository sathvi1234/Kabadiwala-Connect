import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.ai.router import router as ai_router
from app.config import get_settings
from app.database import SessionLocal
from app.models import RecyclerProfile
from app.realtime import version
from app.routers.admin import router as admin_router
from app.routers.auth import router as auth_router
from app.routers.collectors import router as collectors_router
from app.routers.handovers import router as handovers_router
from app.routers.inbox import router as inbox_router
from app.routers.lots import router as lots_router
from app.routers.pickups import router as pickups_router
from app.routers.prices import router as prices_router
from app.routers.public import router as public_router
from app.routers.recyclers import router as recyclers_router
from app.routers.sync import router as sync_router
from app.routers.transactions import router as transactions_router
from app.routers.trust import router as trust_router
from app.services.alerts import evaluate_rules


async def _alert_loop(stop: asyncio.Event):
    while not stop.is_set():
        try:
            db = SessionLocal()
            try:
                evaluate_rules(db)
                if settings.demo_nightly_reset:
                    from app.services.demo import maybe_nightly_reset

                    maybe_nightly_reset(db)
                db.commit()
            finally:
                db.close()
        except Exception:
            pass
        try:
            await asyncio.wait_for(stop.wait(), timeout=300)
        except TimeoutError:
            continue


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from app.database import Base, engine

    from app.database import ensure_columns

    ensure_columns()
    Base.metadata.create_all(engine)
    if settings.is_dev:
        from seed import seed

        seed()
    stop = asyncio.Event()
    task = None if os.environ.get("VERCEL") else asyncio.create_task(_alert_loop(stop))
    yield
    stop.set()
    if task:
        task.cancel()


settings = get_settings()
app = FastAPI(title="Kabadiwala Connect", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (
    auth_router,
    collectors_router,
    prices_router,
    lots_router,
    recyclers_router,
    pickups_router,
    handovers_router,
    transactions_router,
    trust_router,
    admin_router,
    public_router,
    sync_router,
    inbox_router,
    ai_router,
):
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"ok": True, "service": "kabadiwala-connect"}


@app.websocket("/api/ws/availability")
async def availability_ws(socket: WebSocket):
    await socket.accept()
    seen = -1
    try:
        while True:
            current = version
            if current != seen:
                db = SessionLocal()
                try:
                    rows = db.query(RecyclerProfile).filter(RecyclerProfile.status == "approved").all()
                    payload = [{"id": row.user_id, "business_name": row.business_name, "availability": row.availability, "next_slot": row.next_slot} for row in rows]
                finally:
                    db.close()
                await socket.send_json({"recyclers": payload})
                seen = current
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        return
