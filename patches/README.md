# Bekobod Express — V3 Backend

## /start ishlamasligi — diagnostika va to'g'irlash

### 🔥 Eng muhim o'zgarish

`bot.py` to'liq qayta yozildi. **Asosiy farq:** polling endi `asyncio.create_task` ichida ishga tushadi va `lifespan`'ni bloklamaydi.

### Integratsiya qadamlari

#### 1. `app/services/bot.py` — almashtiring (ZIP'dan)

#### 2. `app/main.py` — lifespan'ni yangilang

`patches/004_main_py_example.py` ko'rib, `bot_lifespan()` ni qo'shing:

```python
from contextlib import asynccontextmanager
from app.services.bot import bot_lifespan

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with bot_lifespan():
        yield

app = FastAPI(lifespan=lifespan)
```

**ESLATMA:** mavjud lifespan'da `start_bot()` chaqirilgan bo'lsa **uni o'chiring**. Yangi pattern boshqacha ishlaydi.

#### 3. Diagnostic router'ni include qiling

```python
from app.api.routes import diagnostic
app.include_router(diagnostic.router, prefix="/api/v1")
```

#### 4. Restart va logs ko'rish

```bash
docker-compose restart backend
docker-compose logs -f backend | head -50
```

**Kutilgan loglar:**

```
INFO  | app.services.bot | Bot polling task yaratildi
INFO  | app.services.bot | ✅ Webhook tozalandi
INFO  | app.services.bot | 🤖 Bot @bekobod_express_bot ishga tushdi
INFO  | app.services.bot | 📡 Bot polling boshlanyapti...
```

### /start hali ham ishlamasa — 5 ta sabab

#### Sabab 1: BOT_TOKEN noto'g'ri

```
ERROR | ❌ BOT_TOKEN noto'g'ri (401 Unauthorized)
```

**Yechim:** `.env`'da `BOT_TOKEN`'ni @BotFather'dan qaytadan oling.

#### Sabab 2: WEBAPP_URL HTTPS emas

```
ERROR | ⚠️ WEBAPP_URL HTTPS emas: http://...
```

**Yechim:** Telegram WebApp HTTPS talab qiladi.
- Productionda: Let's Encrypt / Cloudflare proxy
- Localda: `ngrok http 3000` → HTTPS URL'ni `.env`'ga yozing

#### Sabab 3: 409 Conflict (eng ko'p)

```
ERROR | ❌ 409 Conflict: boshqa Bot instance polling qilyapti
```

**Yechim:**

```bash
docker-compose down
docker-compose up -d backend
```

Yoki dev kompyuterda bot ishlayotgan bo'lsa to'xtating.

#### Sabab 4: Tarmoq blokirovkasi

```
ERROR | ❌ Telegram API'ga bog'lanib bo'lmadi
```

**Yechim:**

```bash
docker exec -it <backend-container> sh
curl -v https://api.telegram.org/bot<TOKEN>/getMe
```

Agar timeout — proxy kerak (O'zbekistondan Telegram bot polling ba'zan ishlamaydi):

```env
HTTPS_PROXY=http://your-proxy:3128
```

#### Sabab 5: Lifespan ishga tushmagan

`Bot polling task yaratildi` log'i ko'rinmasa — `main.py`'da `FastAPI(lifespan=lifespan)` bormi tekshiring.

### Diagnostic endpoint chaqirish

```bash
curl -s http://localhost:8000/api/v1/diag/bot | jq
```

Ideal javob: `"status": "ok"`, `issues: []`. Agar issue bo'lsa, har birida `severity` va `msg` aniq xatoni aytadi.

---

## Lokatsiya feature

### Foydalanish flow

1. Yo'lovchi `/start` bosadi
2. Bot 3 ta tugma ko'rsatadi: `🚕 Иловани очиш` / `📍 Жойлашувни юбориш` / `ℹ️ Ёрдам`
3. `📍 Жойлашувни юбориш` → Telegram native lokatsiya dialog'i (xarita yo'q!)
4. Lokatsiya yuboriladi → bot in-memory cache (5 daqiqa)
5. `🚕 Иловани очиш` → WebApp ochiladi
6. NewTripPage `GET /api/v1/users/me/cached-location` chaqiradi
7. Lokatsiya bor bo'lsa → form auto-fill, alert "📍 Telegram orqali yuborilgan joy avtomatik tanlandi"
8. E'lon yuboriladi → `pickup_lat/lng/address` saqlanadi
9. Haydovchi TripDetailPage'da: Yandex static map + Yandex/Google navigator tugmalari

### DB migration

```bash
docker exec -i <postgres-container> psql -U postgres bekobod < patches/001_add_location.sql
```

### Model va schema patch'lari

- `002_trip_model_fields.py` — Trip SQLAlchemy model field'lari
- `003_trip_schemas.py` — Pydantic schema namuna (paired validator bilan)

---

## Production risklari

### 1. In-memory location cache — multi-instance ishlamaydi

`_LOCATION_CACHE` dict bot.py'da. 2+ backend replica bo'lsa, cache miss bo'ladi. Productionda Redis'ga ko'chirish kerak.

### 2. Bot polling — faqat 1 replica

Polling 2 instance'da bo'lsa Telegram 409 qaytaradi. Docker Compose:

```yaml
backend:
  deploy:
    replicas: 1
```

### 3. Yandex Static Maps key

Hozir kalitsiz ishlaydi, kelajakda talab qilishi mumkin. `onError` fallback OSM'ga avtomatik o'tadi.

### 4. `request_location` faqat mobil Telegram'da

Desktop va Telegram Web qo'llab-quvvatlamaydi. Foydalanuvchilarga mobil app tavsiya qiling.

### 5. Eski trip'lar `pickup_lat=NULL` — backward compatible

Frontend `trip.pickup_lat != null` tekshirib, faqat lokatsiya bor trip'larda xarita ko'rsatadi.

---

## Production deploy sequence

```bash
# 1. Backend ZIP'ni server'ga
scp backend-v3.zip server:/tmp/

# 2. Server'da
ssh server
cd /opt/bekobod
unzip /tmp/backend-v3.zip

# 3. Patch'larni qo'lda qo'llash:
#    - 001_add_location.sql → DB
#    - 002 va 003 → model va schema'larga qo'shish

# 4. Build va restart
docker-compose build backend
docker-compose up -d backend

# 5. Logs tekshirish
docker-compose logs -f backend

# 6. Diagnostic
curl https://your-domain.com/api/v1/diag/bot

# 7. Telegram'da /start tekshirish
```
