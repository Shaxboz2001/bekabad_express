from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from app.api.routes import auth, trips, users
from app.models import user, trip, driver_profile  # noqa


# OPTIONS requestlarini to'g'ridan-to'g'ri javob qaytaruvchi middleware
class CORSFixMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            response = Response()
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "*"
            response.headers["Access-Control-Max-Age"] = "86400"
            return response
        response = await call_next(request)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    if True:  # BOT_TOKEN bo'lsa ishga tushirish
        try:
            from app.core.config import settings
            if settings.BOT_TOKEN:
                import asyncio
                from app.services.bot import start_bot, stop_bot
                task = asyncio.create_task(start_bot())
                yield
                task.cancel()
                try:
                    await stop_bot()
                except Exception:
                    pass
            else:
                yield
        except Exception:
            yield
    else:
        yield


app = FastAPI(
    title="Bekobod Express API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# CORS middleware — avval qo'shamiz
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,   # "*" bilan True bo'lmaydi
    allow_methods=["*"],
    allow_headers=["*"],
)

# OPTIONS fix middleware
app.add_middleware(CORSFixMiddleware)

app.include_router(auth.router, prefix="/api")
app.include_router(trips.router, prefix="/api")
app.include_router(users.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.0.0"}