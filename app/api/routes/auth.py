from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from app.db.session import get_db
from app.core.security import (
    verify_password, get_password_hash,
    create_access_token, create_refresh_token, decode_token,
)
from app.models.user import User, UserRole
from app.models.driver_profile import DriverProfile
from app.schemas.user import (
    Token, LoginRequest, UserCreate, UserResponse,
    TelegramAuthRequest, RefreshRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_token(user: User) -> Token:
    """Token + user response yig'ish."""
    return Token(
        access_token=create_access_token({"sub": str(user.id), "role": user.role}),
        refresh_token=create_refresh_token({"sub": str(user.id), "role": user.role}),
        user=user,
    )


@router.post("/register", response_model=UserResponse, status_code=201)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    """Klassik phone+password ro'yxatdan o'tish (admin yoki test uchun)."""
    if db.query(User).filter(User.phone == user_in.phone).first():
        raise HTTPException(400, "Bu telefon raqam ro'yxatdan o'tgan")
    user = User(
        full_name=user_in.full_name,
        phone=user_in.phone,
        hashed_password=get_password_hash(user_in.password),
        role=user_in.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    """Phone+password login — admin va kelajakda boshqa rollar uchun."""
    user = (
        db.query(User)
        .options(joinedload(User.driver_profile))
        .filter(User.phone == data.phone)
        .first()
    )
    if not user or not user.hashed_password or not verify_password(data.password, user.hashed_password):
        raise HTTPException(401, "Telefon yoki parol noto'g'ri")
    if not user.is_active:
        raise HTTPException(403, "Hisob bloklangan")
    return _issue_token(user)


@router.post("/telegram", response_model=Token)
def telegram_auth(data: TelegramAuthRequest, db: Session = Depends(get_db)):
    """
    Telegram orqali avto-kirish va ro'yxatdan o'tish.

    Flow:
      1. telegram_id mavjudmi?
         HA  → ma'lumotlarni yangilab, status'ni tekshirib token beramiz
         YO'Q → role kerak. Yo'q bo'lsa NEED_REGISTRATION

      2. Yangi user yaratish:
         - passenger: faqat phone (ixtiyoriy) → is_verified=True (darhol kiradi)
         - driver: phone (majburiy) + driver_profile (majburiy) → is_verified=False
                   atomik (bitta transaction'da)

      3. Status check:
         - is_active=False → 403 (bloklangan)
         - role=DRIVER + is_verified=False → 403 DRIVER_NOT_VERIFIED
    """

    # ─── 1. Mavjud user ──────────────────────────────────────────────────────
    user = (
        db.query(User)
        .options(joinedload(User.driver_profile))
        .filter(User.telegram_id == data.telegram_id)
        .first()
    )

    if user:
        return _existing_user_login(user, data, db)

    # ─── 2. Yangi user (registration) ────────────────────────────────────────
    if not data.role:
        # Frontend rol so'rashi kerak
        raise HTTPException(status_code=400, detail="NEED_REGISTRATION")

    if data.role == "driver":
        return _register_driver(data, db)
    else:
        return _register_passenger(data, db)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _existing_user_login(user: User, data: TelegramAuthRequest, db: Session) -> Token:
    """Mavjud user uchun: ism/username/phone yangilash, status check, token."""
    changed = False

    if data.full_name and user.full_name != data.full_name:
        user.full_name = data.full_name
        changed = True

    if data.username and user.username != data.username:
        user.username = data.username
        changed = True

    # Telefon yangilash — placeholder o'rniga haqiqiy
    if data.phone and user.phone.startswith("tg_") and not data.phone.startswith("tg_"):
        clash = db.query(User).filter(
            User.phone == data.phone,
            User.id != user.id,
        ).first()
        if clash:
            raise HTTPException(400, "Bu telefon raqam boshqa hisobga biriktirilgan")
        user.phone = data.phone
        changed = True

    if changed:
        try:
            db.commit()
            db.refresh(user)
        except IntegrityError:
            db.rollback()
            raise HTTPException(400, "Ma'lumotlar nomuvofiq")

    # Status check
    if not user.is_active:
        raise HTTPException(403, "Hisobingiz bloklangan. @bekobod_admin bilan bog'laning")

    if user.role == UserRole.DRIVER and not user.is_verified:
        raise HTTPException(403, "DRIVER_NOT_VERIFIED")

    return _issue_token(user)


def _register_passenger(data: TelegramAuthRequest, db: Session) -> Token:
    """Yangi yo'lovchi — telefon ixtiyoriy, darhol verify."""
    phone = _resolve_phone(data, db, required=False)

    user = User(
        telegram_id=data.telegram_id,
        full_name=data.full_name,
        phone=phone,
        username=data.username,
        role=UserRole.PASSENGER,
        is_active=True,
        is_verified=True,  # yo'lovchi darhol kira oladi
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, "Ro'yxatdan o'tishda xato (takroriy ma'lumot)")

    return _issue_token(user)


def _register_driver(data: TelegramAuthRequest, db: Session) -> Token:
    """
    Yangi haydovchi — phone va driver_profile MAJBURIY.
    Atomik: user + driver_profile bitta transaction'da yaratiladi.
    Xato bo'lsa rollback — yarim yaratilgan user qolmaydi.
    """
    if not data.phone:
        raise HTTPException(400, "Telefon raqami majburiy")
    if not data.driver_profile:
        raise HTTPException(400, "Mashina ma'lumotlari majburiy")

    phone = _resolve_phone(data, db, required=True)

    user = User(
        telegram_id=data.telegram_id,
        full_name=data.full_name,
        phone=phone,
        username=data.username,
        role=UserRole.DRIVER,
        is_active=True,
        is_verified=False,  # admin tasdiqlashi kerak
    )
    db.add(user)
    db.flush()  # user.id olish uchun, lekin commit emas

    profile = DriverProfile(
        user_id=user.id,
        **data.driver_profile.model_dump(),
    )
    db.add(profile)

    try:
        db.commit()
        db.refresh(user)
    except IntegrityError as e:
        db.rollback()
        # mashina raqami unique emas, lekin kelajakda bo'lishi mumkin
        raise HTTPException(400, "Ro'yxatdan o'tishda xato. Ma'lumotlarni tekshiring.")

    # Driver yaratildi, lekin verify=False → 403 DRIVER_NOT_VERIFIED
    # Frontend buni "kutilmoqda" ekraniga aylantirishi kerak
    raise HTTPException(403, "DRIVER_NOT_VERIFIED")


def _resolve_phone(data: TelegramAuthRequest, db: Session, required: bool) -> str:
    """
    Telefon raqamni tayyorlash:
      - Berilmagan + required=False → tg_{telegram_id} placeholder
      - Berilmagan + required=True  → 400
      - Berilgan → unique tekshirish, kollizii bo'lsa 400
    """
    if not data.phone:
        if required:
            raise HTTPException(400, "Telefon raqami majburiy")
        return f"tg_{data.telegram_id}"

    # Telefon raqami collision check
    existing = db.query(User).filter(User.phone == data.phone).first()
    if existing:
        raise HTTPException(400, "Bu telefon raqam allaqachon ro'yxatdan o'tgan")

    return data.phone


# ─── Refresh ─────────────────────────────────────────────────────────────────

@router.post("/refresh", response_model=Token)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(401, "Refresh token yaroqsiz")

    user = (
        db.query(User)
        .options(joinedload(User.driver_profile))
        .filter(User.id == int(payload["sub"]))
        .first()
    )
    if not user:
        raise HTTPException(401, "Foydalanuvchi topilmadi")
    if not user.is_active:
        raise HTTPException(403, "Hisob bloklangan")
    if user.role == UserRole.DRIVER and not user.is_verified:
        raise HTTPException(403, "DRIVER_NOT_VERIFIED")

    return _issue_token(user)
