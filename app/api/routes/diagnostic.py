"""
Diagnostic endpoint — bot va WebApp konfiguratsiyasini tekshirish.

Sizning api/routes/__init__.py yoki app/api/__init__.py ichida
bu router'ni include qiling.

Mavjud `app/api/routes/diagnostic.py` faylga qo'shing yoki yangi yarating.
"""
from fastapi import APIRouter, Depends
from app.core.config import settings
from app.services.bot import bot

router = APIRouter(prefix="/diag", tags=["diagnostic"])


@router.get("/bot")
async def bot_status():
    """
    Bot va WebApp konfiguratsiyasini tekshirish.

    Faqat development/staging'da ochiq qoldiring. Productionda admin-only qiling
    (require_admin dependency qo'shing).

    Production tavsiyalar:
      • Endpoint'ni admin auth bilan o'rang
      • Token va URL qisman maskalash (BOT_TOKEN'ning oxirgi 4 belgisi etarli)
    """
    issues = []

    # 1. BOT_TOKEN
    if not settings.BOT_TOKEN:
        issues.append({
            "severity": "error",
            "field": "BOT_TOKEN",
            "msg": ".env'da BOT_TOKEN topilmadi",
        })
    elif len(settings.BOT_TOKEN) < 30:
        issues.append({
            "severity": "warning",
            "field": "BOT_TOKEN",
            "msg": "BOT_TOKEN juda qisqa — to'g'rimi?",
        })

    # 2. WEBAPP_URL
    if not settings.WEBAPP_URL:
        issues.append({
            "severity": "error",
            "field": "WEBAPP_URL",
            "msg": ".env'da WEBAPP_URL yo'q — /start tugmasi ko'rinmaydi",
        })
    elif not settings.WEBAPP_URL.startswith("https://"):
        issues.append({
            "severity": "error",
            "field": "WEBAPP_URL",
            "msg": f"WEBAPP_URL HTTPS emas: {settings.WEBAPP_URL}",
        })

    # 3. Bot connection
    bot_info = None
    if bot:
        try:
            me = await bot.get_me()
            bot_info = {
                "username": me.username,
                "first_name": me.first_name,
                "can_join_groups": me.can_join_groups,
                "supports_inline": me.supports_inline_queries,
            }
        except Exception as e:
            issues.append({
                "severity": "error",
                "field": "bot",
                "msg": f"Bot API'ga bog'lanib bo'lmadi: {e}",
            })
    else:
        issues.append({
            "severity": "error",
            "field": "bot",
            "msg": "Bot instance None — start_bot() chaqirilmagan",
        })

    # 4. Webhook tekshirish
    webhook_info = None
    if bot:
        try:
            wh = await bot.get_webhook_info()
            webhook_info = {
                "url": wh.url,
                "pending_updates": wh.pending_update_count,
                "last_error": wh.last_error_message,
            }
            if wh.url:
                issues.append({
                    "severity": "warning",
                    "field": "webhook",
                    "msg": (
                        f"Webhook o'rnatilgan: {wh.url}. "
                        "Polling rejimida webhook bo'lishi shart emas."
                    ),
                })
        except Exception as e:
            issues.append({
                "severity": "warning",
                "field": "webhook",
                "msg": f"Webhook info olib bo'lmadi: {e}",
            })

    # Token mask qilish
    token_masked = None
    if settings.BOT_TOKEN:
        t = settings.BOT_TOKEN
        token_masked = f"{t[:8]}...{t[-4:]}" if len(t) > 12 else "***"

    return {
        "status": "error" if any(i["severity"] == "error" for i in issues) else "ok",
        "config": {
            "bot_token": token_masked,
            "webapp_url": settings.WEBAPP_URL,
        },
        "bot": bot_info,
        "webhook": webhook_info,
        "issues": issues,
    }
