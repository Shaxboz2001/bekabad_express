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
    "bekobod_to_tashkent": "Бекобод → Тошкент",
    "tashkent_to_bekobod": "Тошкент → Бекобод",
}

CATEGORY_LABELS = {
    "passenger": "Йўловчи",
    "passenger_small_cargo": "Йўловчи + кичик юк",
    "cargo": "Юк ташиш",
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


async def send_telegram_message(
    chat_id: int,
    text: str,
    parse_mode: str = "HTML",
    reply_markup: dict | None = None,
) -> bool:
    """
    Telegram bot orqali xabar yuborish. Xato bo'lsa False qaytaradi (raise qilmaydi).

    Args:
        chat_id: Recipient Telegram ID
        text: HTML formatlangan matn
        parse_mode: "HTML" yoki "MarkdownV2"
        reply_markup: dict — InlineKeyboardMarkup yoki ReplyKeyboardMarkup
                      Format: {"inline_keyboard": [[{"text": "...", "callback_data": "..."}]]}
    """
    if not settings.BOT_TOKEN or not chat_id:
        return False
    try:
        client = await _get_client()
        payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        resp = await client.post(
            f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage",
            json=payload,
        )
        if resp.status_code != 200:
            print(f"Telegram send failed for {chat_id}: {resp.status_code} {resp.text[:200]}")
            return False
        return True
    except Exception as e:
        print(f"Telegram xabar yuborishda xato (chat_id={chat_id}): {e}")
        return False


async def _send_batch(
    chat_ids: list[int],
    text: str,
    reply_markup: dict | None = None,
) -> None:
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
            return await send_telegram_message(chat_id, text, reply_markup=reply_markup)

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
        f"✅ <b>Сизнинг эълонингиз қабул қилинди!</b>\n\n"
        f"📋 <b>Эълон #{trip.id}</b>\n"
        f"🗺 Йўналиш: {direction}\n"
        f"📍 {trip.pickup_point} → {trip.dropoff_point}\n"
        f"🕐 Вақт: {date_str}\n"
        f"💺 Жойлар: {trip.seats} та\n\n"
        f"🚗 <b>Ҳайдовчи маълумотлари:</b>\n"
        f"👤 Исм: {driver.full_name}\n"
        f"📞 Тел: {driver.phone}\n"
        f"🚘 Машина: {profile.car_model} ({profile.car_color or ''})\n"
        f"🔢 Рақам: {profile.car_number}\n"
        f"⭐ Рейтинг: {profile.rating:.1f}\n\n"
        f"💰 Нарх: {trip.total_price:,.0f} сўм\n\n"
        f"Ҳайдовчи билан боғланинг ва йўлга тайёрланинг! 🎉"
    )
    await send_telegram_message(trip.passenger.telegram_id, text)


async def notify_trip_cancelled_passenger(trip: Trip, reason: str = ""):
    """E'lon bekor qilinganda yo'lovchiga xabar"""
    if not trip.passenger or not trip.passenger.telegram_id:
        return

    direction = DIRECTION_LABELS.get(trip.direction.value, trip.direction.value)
    text = (
        f"❌ <b>Эълонингиз бекор қилинди</b>\n\n"
        f"📋 Эълон #{trip.id} | {direction}\n"
        f"📍 {trip.pickup_point} → {trip.dropoff_point}\n"
    )
    if reason:
        text += f"📝 Сабаб: {reason}\n"
    text += "\nЯнги эълон беришингиз мумкин."
    await send_telegram_message(trip.passenger.telegram_id, text)


async def notify_trip_cancelled_driver(trip: Trip, reason: str = ""):
    """E'lon bekor qilinganda haydovchiga xabar"""
    if not trip.driver or not trip.driver.telegram_id:
        return

    direction = DIRECTION_LABELS.get(trip.direction.value, trip.direction.value)
    text = (
        f"❌ <b>Эълон бекор қилинди</b>\n\n"
        f"📋 Эълон #{trip.id} | {direction}\n"
        f"📍 {trip.pickup_point} → {trip.dropoff_point}\n"
    )
    if reason:
        text += f"📝 Сабаб: {reason}\n"
    await send_telegram_message(trip.driver.telegram_id, text)


async def notify_new_trip_to_drivers(trip: Trip, driver_telegram_ids: list[int]):
    """
    Yangi e'lon berilganda barcha tasdiqlangan haydovchilarga parallel xabar.

    Inline tugma orqali to'g'ridan-to'g'ri qabul qilish mumkin —
    bot.py'dagi callback_query handler tripni qabul qiladi.
    """
    if not driver_telegram_ids:
        return

    direction = DIRECTION_LABELS.get(trip.direction.value, trip.direction.value)
    category = CATEGORY_LABELS.get(trip.category.value, trip.category.value)
    date_str = trip.trip_date.strftime("%d.%m.%Y %H:%M")

    text = (
        f"🆕 <b>Янги эълон!</b>\n\n"
        f"📋 Эълон #{trip.id}\n"
        f"🗺 {direction}\n"
        f"📍 <b>{trip.pickup_point}</b> → <b>{trip.dropoff_point}</b>\n"
        f"🕐 Вақт: {date_str}\n"
        f"💺 Жойлар: {trip.seats} та\n"
        f"📦 Тоифа: {category}\n"
        f"💰 Нарх: {trip.total_price:,.0f} сўм\n"
    )
    if trip.notes:
        text += f"📝 Изоҳ: {trip.notes}\n"
    if trip.luggage:
        text += "🧳 Юк бор\n"

    # Lokatsiya bor bo'lsa qayd qilamiz
    if getattr(trip, 'pickup_lat', None) and getattr(trip, 'pickup_lng', None):
        text += "📍 Аниқ жой белгиланган (қабул қилгач кўрасиз)\n"

    # ─── Inline keyboard ─────────────────────────────────────────────────────
    # Strategy A: web_app tugmasi → WebApp ochiladi va URL parameter orqali
    # avtomatik trip qabul qilinadi (frontend `/auth?accept=<trip_id>` route).
    #
    # Bu callback_data'dan yaxshiroq:
    #   • Bir bosishda hamma narsa bo'ladi (qabul + WebApp ochilishi)
    #   • Foydalanuvchi haydovchi info, mashina detallarini darhol ko'radi
    #   • Native Telegram WebApp UX
    #
    # web_app URL HTTPS bo'lishi shart (Telegram talabi).
    webapp_url = settings.WEBAPP_URL
    if webapp_url and webapp_url.startswith("https://"):
        # Trip ID'ni query parameter sifatida qo'shamiz
        # Frontend `?accept=<id>` ni o'qib, login bo'lgach trip'ni accept qiladi
        accept_url = f"{webapp_url.rstrip('/')}/?accept={trip.id}"
        reply_markup = {
            "inline_keyboard": [[
                {
                    "text": "✅ Қабул қилиш",
                    "web_app": {"url": accept_url},
                }
            ]]
        }
    else:
        # Fallback: callback_data (HTTPS WEBAPP_URL bo'lmasa)
        reply_markup = {
            "inline_keyboard": [[
                {
                    "text": "✅ Қабул қилиш",
                    "callback_data": f"accept_trip:{trip.id}",
                }
            ]]
        }

    await _send_batch(driver_telegram_ids, text, reply_markup=reply_markup)


async def notify_trip_completed(trip: Trip):
    """Safar yakunlanganda yo'lovchiga xabar"""
    if not trip.passenger or not trip.passenger.telegram_id:
        return

    text = (
        f"🏁 <b>Сафар якунланди!</b>\n\n"
        f"📋 Эълон #{trip.id}\n"
        f"💰 Тўлов: {trip.total_price:,.0f} сўм\n\n"
        f"Хизматдан фойдаланганингиз учун раҳмат! 🙏"
    )
    await send_telegram_message(trip.passenger.telegram_id, text)


# ─── User verification notifications ─────────────────────────────────────────

async def notify_driver_verified(user: User):
    """Admin haydovchini tasdiqlaganda xabar"""
    if not user.telegram_id:
        return

    text = (
        f"✅ <b>Тасдиқландингиз!</b>\n\n"
        f"Салом, <b>{user.full_name}</b>!\n\n"
        f"Сизнинг ҳайдовчи ҳисобингиз админ томонидан тасдиқланди. "
        f"Энди эълонларни қабул қилиб, ишлай оласиз.\n\n"
        f"📱 Иловага ўтинг ва биринчи эълонни қабул қилинг 👇\n"
        f"{settings.WEBAPP_URL}"
    )
    await send_telegram_message(user.telegram_id, text)


async def notify_driver_rejected(user: User):
    """Admin haydovchini rad etganda xabar"""
    if not user.telegram_id:
        return

    text = (
        f"❌ <b>Ҳисобингиз тасдиқланмади</b>\n\n"
        f"Афсуски, сизнинг ҳайдовчи ҳисобингиз админ томонидан тасдиқланмади.\n\n"
        f"📞 Қўшимча маълумот учун: @bekobod_admin"
    )
    await send_telegram_message(user.telegram_id, text)


# ─── Cleanup (optional, lifespan shutdown'da chaqirilsa yaxshi) ──────────────

async def close_telegram_client():
    """Application shutdown'da chaqirilishi kerak — connection'lar to'g'ri yopiladi."""
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None
