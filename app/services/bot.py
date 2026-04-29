"""
Telegram Bot — aiogram 3.x

Asosiy o'zgarishlar (V3):
  • Polling alohida asyncio.Task'da ishlaydi (FastAPI'ni bloklamaydi)
  • Detailed logging — har qaysi qadam log'ga yoziladi
  • Webhook avtomatik tozalanadi (409 Conflict'ni oldini olish)
  • Diagnostic info bot startup paytida yoziladi
  • Lokatsiya handler — yo'lovchi joyni yuborsa Redis'ga 5 daqiqaga saqlaydi
    (keyingi e'lon yaratilganda WebApp avtomatik shu joyni ishlatishi uchun)

Startup pattern (FastAPI lifespan):

    from contextlib import asynccontextmanager
    from app.services.bot import bot_lifespan

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with bot_lifespan():
            yield

    app = FastAPI(lifespan=lifespan)
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramConflictError, TelegramUnauthorizedError
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    WebAppInfo, ReplyKeyboardMarkup, KeyboardButton,
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from app.core.config import settings

logger = logging.getLogger(__name__)

# ─── Singletons ──────────────────────────────────────────────────────────────
bot: Optional[Bot] = None
dp = Dispatcher()
_polling_task: Optional[asyncio.Task] = None


def _init_bot() -> Optional[Bot]:
    """Bot instance singleton."""
    global bot
    if bot is not None:
        return bot
    if not settings.BOT_TOKEN:
        logger.error("❌ BOT_TOKEN .env'da yo'q — bot ishga tushmaydi")
        return None
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    return bot


# ─── Klaviaturalar ───────────────────────────────────────────────────────────
def main_keyboard(webapp_url: str) -> ReplyKeyboardMarkup:
    """
    Asosiy klaviatura — faqat WebApp va Yordam.

    Lokatsiya tugmasi YO'Q: lokatsiya WebApp ichida `tg.LocationManager`
    orqali olinadi (e'lon berish paytida).
    """
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(
            text="🚕 Иловани очиш",
            web_app=WebAppInfo(url=webapp_url),
        )
    )
    builder.row(KeyboardButton(text="ℹ️ Ёрдам"))
    return builder.as_markup(resize_keyboard=True)


def contact_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(
            text="📞 Телефон рақамни улашиш",
            request_contact=True,
        )
    )
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


# ─── Handlers ────────────────────────────────────────────────────────────────
@dp.message(CommandStart())
async def start_handler(message: types.Message):
    logger.info(f"/start from user_id={message.from_user.id}")
    user = message.from_user
    name = user.full_name or user.first_name or "Дўст"

    webapp_url = settings.WEBAPP_URL
    if not webapp_url:
        await message.answer(
            f"Салом, <b>{name}</b>! 👋\n\n"
            "⚠️ Илова URL'и созланмаган. Админ билан боғланинг."
        )
        logger.error("WEBAPP_URL settings'da yo'q")
        return

    if not webapp_url.startswith("https://"):
        await message.answer(
            f"Салом, <b>{name}</b>! 👋\n\n"
            f"⚠️ Илова HTTPS орқали ишлаши керак.\nҲозирги: {webapp_url}\n"
            "Админ билан боғланинг."
        )
        logger.error(f"WEBAPP_URL HTTPS emas: {webapp_url}")
        return

    text = (
        f"Салом, <b>{name}</b>! 👋\n\n"
        f"<b>Bekobod Express</b> — Бекобод ↔ Тошкент йўналишида "
        f"қулай ва ишончли сафар тизими.\n\n"
        f"🚕 Йўловчи бўлиб эълон беринг — ҳайдовчилар кўради\n"
        f"🚗 Ҳайдовчи бўлиб ишланг — қўшимча даромад\n\n"
        f"Пастдаги тугмани босинг 👇"
    )
    await message.answer(text, reply_markup=main_keyboard(webapp_url))


@dp.message(F.text == "ℹ️ Ёрдам")
@dp.message(Command("help"))
async def help_handler(message: types.Message):
    text = (
        "📋 <b>Қўлланма:</b>\n\n"
        "1️⃣ <b>Рўйхатдан ўтиш:</b>\n"
        "   • Йўловчи: телефонни киритинг ва эълон беринг\n"
        "   • Ҳайдовчи: телефон + машина маълумотлари,\n"
        "     админ тасдиқлагач ишлай оласиз\n\n"
        "2️⃣ <b>Эълон бериш (йўловчи):</b>\n"
        "   • Илова ичида йўналиш, вақт, жойни танланг\n"
        "   • 📍 тугмаси орқали айни жойингизни юборишингиз мумкин\n"
        "   • Ҳайдовчи қабул қилса, хабар келади 📩\n\n"
        "3️⃣ <b>Эълон қабул қилиш (ҳайдовчи):</b>\n"
        "   Янги эълонлар ҳақида хабар оласиз\n"
        "   Илова ичида қабул қилинг\n\n"
        "📞 Муаммо бўлса: @bekobod_admin"
    )
    await message.answer(text)


@dp.message(Command("contact"))
async def contact_request_handler(message: types.Message):
    await message.answer(
        "Телефон рақамингизни улашинг — биз уни хавфсиз сақлаймиз ва "
        "ҳайдовчиларга кўрсатамиз (эълон қабул қилингач).",
        reply_markup=contact_keyboard(),
    )


@dp.message(F.contact)
async def contact_received_handler(message: types.Message):
    contact = message.contact
    if contact.user_id != message.from_user.id:
        await message.answer("⚠️ Фақат ўз телефонингизни улашинг")
        return
    await message.answer(
        f"✅ Телефон қабул қилинди: <code>{contact.phone_number}</code>\n\n"
        f"Энди иловани очинг ва давом этинг 👇",
        reply_markup=main_keyboard(settings.WEBAPP_URL or ""),
    )


@dp.message(F.location)
async def location_handler(message: types.Message):
    """
    Eski tugma yoki Telegram menyusidan lokatsiya yuborilgan bo'lsa.

    Yangi flow: lokatsiya WebApp ichida `tg.LocationManager` orqali
    olinadi (e'lon berish paytida). Bu yerda faqat foydalanuvchini
    iliuzaga yo'naltiramiz.
    """
    await message.answer(
        "📍 Жойлашув илова ичида автоматик олинади.\n\n"
        "Иловани очинг ва эълон бераётганда «📍 Айни жойим» тугмасини босинг 👇",
        reply_markup=main_keyboard(settings.WEBAPP_URL or ""),
    )


@dp.message(F.web_app_data)
async def web_app_data_handler(message: types.Message):
    data = message.web_app_data.data
    await message.answer(f"✅ Маълумот қабул қилинди: {data}")


# Generic fallback — ESLATMA: bu eng oxirgi handler bo'lishi shart.
# Avvalgi handler'lardan birortasi match qilmasa, shu ishlaydi.
@dp.message()
async def fallback_handler(message: types.Message):
    logger.debug(f"Fallback: text={message.text!r} from {message.from_user.id}")
    await message.answer(
        "Тушунмадим. /start босинг ёки илова тугмасини босинг 👇",
        reply_markup=main_keyboard(settings.WEBAPP_URL or ""),
    )


# ─── Public API: hozircha kerak emas ─────────────────────────────────────────
# Avvalgi versiyada bot orqali yuborilgan lokatsiyani cache'lash bor edi.
# Endi lokatsiya WebApp ichida olinadi, shuning uchun bu kerak emas.
# Backward compat uchun stub qoldiramiz (chaqiruvchi kod crash bo'lmasligi uchun).
def get_cached_location(telegram_id: int):
    return None


def consume_cached_location(telegram_id: int):
    return None


# ─── Lifecycle (FastAPI lifespan'dan chaqiriladi) ────────────────────────────
async def _polling_runner():
    """
    Polling forever loop. Background task'da ishlaydi.

    aiogram exception'lari:
      • TelegramConflictError — boshqa instance polling qilyapti
      • TelegramUnauthorizedError — token noto'g'ri
      • Tarmoq xatolari — aiogram avtomatik retry qiladi
    """
    b = _init_bot()
    if b is None:
        logger.error("Bot instance None — polling boshlanmaydi")
        return

    # WEBAPP_URL diagnostika
    if not settings.WEBAPP_URL:
        logger.error("⚠️  WEBAPP_URL .env'da yo'q — /start tugmasi ko'rinmaydi")
    elif not settings.WEBAPP_URL.startswith("https://"):
        logger.error(
            f"⚠️  WEBAPP_URL HTTPS emas: {settings.WEBAPP_URL}"
        )

    # Webhook'ni majburan tozalash — polling boshlanishi uchun shart
    try:
        await b.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Webhook tozalandi")
    except Exception as e:
        logger.warning(f"Webhook tozalashda xato (e'tiborsiz): {e}")

    # Bot identifikatsiyasi — token to'g'ri ekanligini tasdiqlaydi
    try:
        me = await b.get_me()
        logger.info(
            f"🤖 Bot @{me.username} (id={me.id}) ishga tushdi. "
            f"WebApp: {settings.WEBAPP_URL}"
        )
    except TelegramUnauthorizedError:
        logger.error(
            "❌ BOT_TOKEN noto'g'ri (401 Unauthorized). "
            ".env'da BOT_TOKEN'ni tekshiring."
        )
        return
    except Exception as e:
        logger.error(
            f"❌ Telegram API'ga bog'lanib bo'lmadi: {e}\n"
            "Tarmoq sozlamalarini tekshiring (firewall, proxy)."
        )
        return

    # Polling — forever loop
    try:
        logger.info("📡 Bot polling boshlanyapti...")
        await dp.start_polling(
            b,
            allowed_updates=dp.resolve_used_update_types(),
            handle_signals=False,  # FastAPI o'z signal handler'ini ishlatadi
        )
    except TelegramConflictError as e:
        logger.error(
            f"❌ 409 Conflict: boshqa Bot instance polling qilyapti.\n"
            f"  • Faqat 1 ta jarayonda bot ishga tushiring\n"
            f"  • Eski docker container'ni o'chiring: docker ps && docker kill <id>\n"
            f"Detail: {e}"
        )
    except asyncio.CancelledError:
        logger.info("Bot polling cancelled (graceful shutdown)")
        raise
    except Exception as e:
        logger.exception(f"❌ Bot polling crash: {e}")


@asynccontextmanager
async def bot_lifespan():
    """
    FastAPI lifespan'da ishlatiladigan async context manager.

    Pattern:
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            async with bot_lifespan():
                yield

    `start_polling` forever loop bo'lgani uchun uni `asyncio.create_task`
    ichida ishga tushiramiz — bu FastAPI'ni bloklamaydi.
    """
    global _polling_task

    # Polling'ni alohida task'da ishga tushiramiz
    _polling_task = asyncio.create_task(_polling_runner(), name="bot-polling")
    logger.info("Bot polling task yaratildi")

    try:
        yield
    finally:
        # Graceful shutdown
        if _polling_task and not _polling_task.done():
            logger.info("Bot polling to'xtatilmoqda...")
            _polling_task.cancel()
            try:
                await asyncio.wait_for(_polling_task, timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

        if bot:
            await bot.session.close()
            logger.info("Bot session yopildi")


# ─── Backward compatibility ──────────────────────────────────────────────────
# Eski `start_bot()`/`stop_bot()` chaqiriladigan joylar uchun
async def start_bot():
    """DEPRECATED: bot_lifespan() ishlating."""
    logger.warning("start_bot() deprecated. Use bot_lifespan() in FastAPI lifespan.")
    await _polling_runner()


async def stop_bot():
    """DEPRECATED: bot_lifespan() ishlating."""
    if _polling_task and not _polling_task.done():
        _polling_task.cancel()
    if bot:
        await bot.session.close()
