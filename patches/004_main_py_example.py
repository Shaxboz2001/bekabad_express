"""
FastAPI main.py — bot integratsiyasi NAMUNASI

Sizning mavjud `app/main.py` faylida bot ishga tushadigan joyni quyidagi
pattern'ga aylantiring.

ESLATMA: bu to'liq fayl emas — sizning loyihangizdagi mavjud import'lar va
router include'larini saqlang. Faqat lifespan qismini almashtiring.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.services.bot import bot_lifespan

# Sizning router'laringiz:
# from app.api.routes import auth, trips, users, diagnostic
# from app.db.session import engine
# from app.db.base import Base

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan: startup → yield → shutdown.

    Bot polling alohida asyncio.Task'da ishga tushadi va FastAPI'ni
    bloklamaydi. Shutdown'da graceful cancel qilinadi.
    """
    logger.info("🚀 Backend ishga tushyapti...")

    # DB initial setup (agar kerak bo'lsa)
    # async with engine.begin() as conn:
    #     await conn.run_sync(Base.metadata.create_all)

    # Bot lifecycle — context manager
    async with bot_lifespan():
        logger.info("✅ Backend tayyor")
        yield  # ← FastAPI shu yerda request'larni qabul qila boshlaydi

    logger.info("👋 Backend to'xtatilmoqda...")


app = FastAPI(
    title="Bekobod Express API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router'lar
# app.include_router(auth.router, prefix="/api/v1")
# app.include_router(trips.router, prefix="/api/v1")
# app.include_router(users.router, prefix="/api/v1")
# app.include_router(diagnostic.router, prefix="/api/v1")  # ← yangi


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
