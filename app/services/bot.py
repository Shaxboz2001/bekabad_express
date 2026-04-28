"""
Telegram Bot - aiogram 3.x

Flow:
  /start   → Salom + WebApp tugmasi (asosiy yo'l)
  /contact → Agar WebApp'da contact request ishlamasa fallback sifatida
"""
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    WebAppInfo, ReplyKeyboardMarkup, KeyboardButton,
    KeyboardButtonRequestUser, ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from app.core.config import settings

bot = Bot(token=settings.BOT_TOKEN) if settings.BOT_TOKEN else None
dp = Dispatcher()


def main_keyboard(webapp_url: str) -> ReplyKeyboardMarkup:
    """Asosiy WebApp tugmasi."""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(
            text="🚕 Ilovani ochish",
            web_app=WebAppInfo(url=webapp_url),
        )
    )
    builder.row(KeyboardButton(text="ℹ️ Yordam"))
    return builder.as_markup(resize_keyboard=True)


def contact_keyboard() -> ReplyKeyboardMarkup:
    """Telefon ulashish tugmasi (fallback uchun)."""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(
            text="📞 Telefon raqamni ulashish",
            request_contact=True,
        )
    )
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


@dp.message(CommandStart())
async def start_handler(message: types.Message):
    user = message.from_user
    name = user.full_name or user.first_name or "Do'st"

    text = (
        f"Salom, <b>{name}</b>! 👋\n\n"
        f"<b>Bekobod Express</b> — Bekobod ↔ Toshkent yo'nalishida "
        f"qulay va ishonchli safar tizimi.\n\n"
        f"🚕 Yo'lovchi bo'lib e'lon bering — haydovchilar ko'radi\n"
        f"🚗 Haydovchi bo'lib ishlang — qo'shimcha daromad\n\n"
        f"Pastdagi tugmani bosing 👇"
    )

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=main_keyboard(settings.WEBAPP_URL),
    )


@dp.message(F.text == "ℹ️ Yordam")
async def help_handler(message: types.Message):
    text = (
        "📋 <b>Qo'llanma:</b>\n\n"
        "1️⃣ <b>Ro'yxatdan o'tish:</b>\n"
        "   • Yo'lovchi: telefonni ulashing va e'lon bering\n"
        "   • Haydovchi: telefon + mashina ma'lumotlari kiriting,\n"
        "     admin tasdiqlagach ishlay olasiz\n\n"
        "2️⃣ <b>E'lon berish (yo'lovchi):</b>\n"
        "   Yo'nalish, vaqt, joy sonini tanlang\n"
        "   Haydovchi qabul qilsa Telegram'ga xabar keladi 📩\n\n"
        "3️⃣ <b>E'lon qabul qilish (haydovchi):</b>\n"
        "   Yangi e'lonlar haqida xabar olasiz\n"
        "   Ilovada qabul qilib, yo'lovchi bilan bog'laning\n\n"
        "4️⃣ <b>Narxlar:</b>\n"
        "   Bekobod ↔ Toshkent: avtomatik hisoblanadi\n\n"
        "📞 Muammo bo'lsa: @bekobod_admin"
    )
    await message.answer(text, parse_mode="HTML")


@dp.message(Command("contact"))
async def contact_request_handler(message: types.Message):
    """
    Fallback: agar WebApp'da contact request ishlamasa, bot orqali olamiz.
    Bu juda kam holatda kerak bo'ladi (eski Telegram clientlari).
    """
    await message.answer(
        "Telefon raqamingizni ulashing — biz uni xavfsiz saqlaymiz va "
        "haydovchilarga ko'rsatamiz (e'lon qabul qilingach).",
        reply_markup=contact_keyboard(),
    )


@dp.message(F.contact)
async def contact_received_handler(message: types.Message):
    """
    Telefon ulashildi — bu ma'lumotni hozircha faqat tasdiqlash uchun
    ishlatamiz. Asosiy registratsiya WebApp ichida bo'ladi.

    Production'da: bu yerda backend'ga POST qilib telefonni saqlash kerak,
    yoki Redis'da `tg_id → phone` mapping qo'yish kerak.
    """
    contact = message.contact
    if contact.user_id != message.from_user.id:
        await message.answer("⚠️ Faqat o'z telefoningizni ulashing")
        return

    await message.answer(
        f"✅ Telefon qabul qilindi: <code>{contact.phone_number}</code>\n\n"
        f"Endi ilovani oching va davom eting 👇",
        parse_mode="HTML",
        reply_markup=main_keyboard(settings.WEBAPP_URL),
    )


@dp.message(F.web_app_data)
async def web_app_data_handler(message: types.Message):
    """Mini App dan kelgan ma'lumotlar (kelajakda kerak bo'lsa)."""
    data = message.web_app_data.data
    await message.answer(f"✅ Ma'lumot qabul qilindi: {data}")


# ─── Lifecycle ───────────────────────────────────────────────────────────────

async def start_bot():
    """Bot ni ishga tushirish (lifespan'da chaqiriladi)."""
    if not settings.BOT_TOKEN:
        print("⚠️  BOT_TOKEN .env da yo'q — bot ishlamaydi")
        return
    print("🤖 Telegram bot ishga tushdi...")
    await dp.start_polling(bot, skip_updates=True)


async def stop_bot():
    if bot:
        await bot.session.close()
