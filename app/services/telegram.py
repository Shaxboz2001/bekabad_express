"""
Telegram bot notification service.
Haydovchi e'lonni qabul qilganda yoki status o'zgarganda
foydalanuvchiga va haydovchiga xabar yuboradi.
"""
import asyncio
import httpx
from app.core.config import settings
from app.models.trip import Trip
from app.models.user import User

DIRECTION_LABELS = {
    "bekobod_to_tashkent": "Bekobod → Toshkent",
    "tashkent_to_bekobod": "Toshkent → Bekobod",
}

CATEGORY_LABELS = {
    "passenger": "Yo'lovchi",
    "passenger_small_cargo": "Yo'lovchi + kichik yuk",
    "cargo": "Yuk tashish",
}

# Telegram Bot API rate-limit: 30 message/second per bot.
# Semaphore — concurrent so'rovlar sonini cheklash (rate-limit himoyasi).
_TELEGRAM_CONCURRENCY = 20

# Single httpx client — connection pool qayta ishlatiladi.
# Har xabar uchun yangi client yaratish — TLS handshake overhead'i.
_client: httpx.AsyncClient | None = None


async def _get_client() -> httpx.AsyncClient:
    """Lazy global httpx client. Bir marta yaratiladi, qayta ishlatiladi."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=10,
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        )
    return _client


async def send_telegram_message(chat_id: int, text: str, parse_mode: str = "HTML") -> bool:
    """Telegram bot orqali xabar yuborish. Xato bo'lsa False qaytaradi (raise qilmaydi)."""
    if not settings.BOT_TOKEN or not chat_id:
        return False
    try:
        client = await _get_client()
        resp = await client.post(
            f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
        )
        if resp.status_code != 200:
            # 403 (user blocked bot), 400 (chat not found) va h.k. — log uchun
            print(f"Telegram send failed for {chat_id}: {resp.status_code} {resp.text[:200]}")
            return False
        return True
    except Exception as e:
        print(f"Telegram xabar yuborishda xato (chat_id={chat_id}): {e}")
        return False


async def _send_batch(chat_ids: list[int], text: str) -> None:
    """
    Bir nechta foydalanuvchiga parallel xabar yuborish.
    Semaphore bilan rate-limit himoyasi.
    return_exceptions=True — birorta xato qolganlarni to'xtatmaydi.
    """
    if not chat_ids:
        return

    semaphore = asyncio.Semaphore(_TELEGRAM_CONCURRENCY)

    async def _send_one(chat_id: int) -> bool:
        async with semaphore:
            return await send_telegram_message(chat_id, text)

    await asyncio.gather(
        *(_send_one(cid) for cid in chat_ids),
        return_exceptions=True,
    )


# ─── Trip notifications ──────────────────────────────────────────────────────

async def notify_trip_accepted(trip: Trip):
    """Haydovchi e'lonni qabul qilganda yo'lovchiga xabar"""
    if not trip.passenger or not trip.passenger.telegram_id:
        return
    if not trip.driver or not trip.driver.driver_profile:
        return

    driver = trip.driver
    profile = driver.driver_profile
    direction = DIRECTION_LABELS.get(trip.direction.value, trip.direction.value)
    date_str = trip.trip_date.strftime("%d.%m.%Y %H:%M")

    text = (
        f"✅ <b>Sizning e'loningiz qabul qilindi!</b>\n\n"
        f"📋 <b>E'lon #{trip.id}</b>\n"
        f"🗺 Yo'nalish: {direction}\n"
        f"📍 {trip.pickup_point} → {trip.dropoff_point}\n"
        f"🕐 Vaqt: {date_str}\n"
        f"💺 Joylar: {trip.seats} ta\n\n"
        f"🚗 <b>Haydovchi ma'lumotlari:</b>\n"
        f"👤 Ism: {driver.full_name}\n"
        f"📞 Tel: {driver.phone}\n"
        f"🚘 Mashina: {profile.car_model} ({profile.car_color or ''})\n"
        f"🔢 Raqam: {profile.car_number}\n"
        f"⭐ Reyting: {profile.rating:.1f}\n\n"
        f"💰 Narx: {trip.total_price:,.0f} so'm\n\n"
        f"Haydovchi bilan bog'laning va yo'lga tayyorlaning! 🎉"
    )
    await send_telegram_message(trip.passenger.telegram_id, text)


async def notify_trip_cancelled_passenger(trip: Trip, reason: str = ""):
    """E'lon bekor qilinganda yo'lovchiga xabar"""
    if not trip.passenger or not trip.passenger.telegram_id:
        return

    direction = DIRECTION_LABELS.get(trip.direction.value, trip.direction.value)
    text = (
        f"❌ <b>E'loningiz bekor qilindi</b>\n\n"
        f"📋 E'lon #{trip.id} | {direction}\n"
        f"📍 {trip.pickup_point} → {trip.dropoff_point}\n"
    )
    if reason:
        text += f"📝 Sabab: {reason}\n"
    text += "\nYangi e'lon berishingiz mumkin."
    await send_telegram_message(trip.passenger.telegram_id, text)


async def notify_trip_cancelled_driver(trip: Trip, reason: str = ""):
    """E'lon bekor qilinganda haydovchiga xabar"""
    if not trip.driver or not trip.driver.telegram_id:
        return

    direction = DIRECTION_LABELS.get(trip.direction.value, trip.direction.value)
    text = (
        f"❌ <b>E'lon bekor qilindi</b>\n\n"
        f"📋 E'lon #{trip.id} | {direction}\n"
        f"📍 {trip.pickup_point} → {trip.dropoff_point}\n"
    )
    if reason:
        text += f"📝 Sabab: {reason}\n"
    await send_telegram_message(trip.driver.telegram_id, text)


async def notify_new_trip_to_drivers(trip: Trip, driver_telegram_ids: list[int]):
    """
    Yangi e'lon berilganda barcha haydovchilarga parallel xabar.
    50 haydovchi: ~3-5 sekund (sequential 50s o'rniga).
    """
    if not driver_telegram_ids:
        return

    direction = DIRECTION_LABELS.get(trip.direction.value, trip.direction.value)
    category = CATEGORY_LABELS.get(trip.category.value, trip.category.value)
    date_str = trip.trip_date.strftime("%d.%m.%Y %H:%M")

    text = (
        f"🆕 <b>Yangi e'lon!</b>\n\n"
        f"📋 E'lon #{trip.id}\n"
        f"🗺 {direction}\n"
        f"📍 <b>{trip.pickup_point}</b> → <b>{trip.dropoff_point}</b>\n"
        f"🕐 Vaqt: {date_str}\n"
        f"💺 Joylar: {trip.seats} ta\n"
        f"📦 Kategoriya: {category}\n"
        f"💰 Narx: {trip.total_price:,.0f} so'm\n"
    )
    if trip.notes:
        text += f"📝 Izoh: {trip.notes}\n"
    if trip.luggage:
        text += "🧳 Yuk bor\n"

    text += f"\nQabul qilish uchun ilovaga o'ting 👇\n{settings.WEBAPP_URL}"

    await _send_batch(driver_telegram_ids, text)


async def notify_trip_completed(trip: Trip):
    """Safar yakunlanganda yo'lovchiga xabar"""
    if not trip.passenger or not trip.passenger.telegram_id:
        return

    text = (
        f"🏁 <b>Safar yakunlandi!</b>\n\n"
        f"📋 E'lon #{trip.id}\n"
        f"💰 To'lov: {trip.total_price:,.0f} so'm\n\n"
        f"Xizmatdan foydalanganingiz uchun rahmat! 🙏"
    )
    await send_telegram_message(trip.passenger.telegram_id, text)


# ─── User verification notifications ─────────────────────────────────────────

async def notify_driver_verified(user: User):
    """Admin haydovchini tasdiqlaganda xabar"""
    if not user.telegram_id:
        return

    text = (
        f"✅ <b>Tasdiqlandingiz!</b>\n\n"
        f"Salom, <b>{user.full_name}</b>!\n\n"
        f"Sizning haydovchi hisobingiz admin tomonidan tasdiqlandi. "
        f"Endi e'lonlarni qabul qilib, ishlay olasiz.\n\n"
        f"📱 Ilovaga o'ting va birinchi e'lonni qabul qiling 👇\n"
        f"{settings.WEBAPP_URL}"
    )
    await send_telegram_message(user.telegram_id, text)


async def notify_driver_rejected(user: User):
    """Admin haydovchini rad etganda xabar"""
    if not user.telegram_id:
        return

    text = (
        f"❌ <b>Hisobingiz tasdiqlanmadi</b>\n\n"
        f"Afsuski, sizning haydovchi hisobingiz admin tomonidan tasdiqlanmadi.\n\n"
        f"📞 Qo'shimcha ma'lumot uchun: @bekobod_admin"
    )
    await send_telegram_message(user.telegram_id, text)


# ─── Cleanup (optional, lifespan shutdown'da chaqirilsa yaxshi) ──────────────

async def close_telegram_client():
    """Application shutdown'da chaqirilishi kerak — connection'lar to'g'ri yopiladi."""
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None
