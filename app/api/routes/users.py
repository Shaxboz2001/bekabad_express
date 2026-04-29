from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from typing import Optional
from app.db.session import get_db
from app.api.deps import get_current_user, require_admin
from app.models.user import User, UserRole
from app.models.driver_profile import DriverProfile
from app.schemas.user import (
    UserResponse, UserCreate, UserUpdate,
    DriverProfileCreate, DriverProfileUpdate, DriverProfileResponse
)
from app.core.security import get_password_hash
from app.services.telegram import (
    notify_driver_verified, notify_driver_rejected,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(User).options(joinedload(User.driver_profile)).filter(User.id == current_user.id).first()


@router.get("/me/cached-location")
def get_cached_location(current_user: User = Depends(get_current_user)):
    """
    Telegram orqali yuborilgan oxirgi lokatsiyani qaytaradi (5 daqiqa ichida).

    Frontend NewTripPage'da chaqiriladi — agar foydalanuvchi yaqinda
    Telegram'da 📍 tugmasini bosgan bo'lsa, lokatsiya avtomatik form'ga
    to'ldiriladi.

    Read-only — ma'lumot o'chirilmaydi (e'lon yaratilganda consume qilinadi).
    """
    from app.services.bot import get_cached_location as bot_get_loc
    if not current_user.telegram_id:
        return {"location": None}
    loc = bot_get_loc(current_user.telegram_id)
    if not loc:
        return {"location": None}
    return {
        "location": {
            "lat": loc[0],
            "lng": loc[1],
        }
    }


@router.get("/", response_model=list[UserResponse])
def list_users(
    role: Optional[UserRole] = None,
    is_verified: Optional[bool] = None,
    is_active: Optional[bool] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=500),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    """
    Admin uchun foydalanuvchilar ro'yxati.
    is_verified=false → tasdiq kutayotganlar (admin panelda 'Pending' tab uchun)
    """
    q = db.query(User).options(joinedload(User.driver_profile))
    if role is not None:
        q = q.filter(User.role == role)
    if is_verified is not None:
        q = q.filter(User.is_verified == is_verified)
    if is_active is not None:
        q = q.filter(User.is_active == is_active)
    return q.order_by(User.created_at.desc()).offset((page - 1) * size).limit(size).all()


@router.post("/", response_model=UserResponse, status_code=201)
def create_user(body: UserCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    if db.query(User).filter(User.phone == body.phone).first():
        raise HTTPException(400, "Telefon raqam ro'yxatdan o'tgan")
    user = User(
        full_name=body.full_name, phone=body.phone, role=body.role,
        hashed_password=get_password_hash(body.password),
        # Admin tomondan yaratilgan user darhol tasdiqlangan
        is_verified=True,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}", response_model=UserResponse)
def update_user(user_id: int, body: UserUpdate, db: Session = Depends(get_db), _=Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "Foydalanuvchi topilmadi")

    # exclude_unset: faqat aniq jo'natilgan maydonlar; None'ni ham qo'llaydi
    # (masalan, phone=None bilan tozalash kerak bo'lsa)
    payload = body.model_dump(exclude_unset=True)
    for k, v in payload.items():
        setattr(user, k, v)
    db.commit()
    db.refresh(user)
    return user


# ─── Verify / Reject / Unblock — admin uchun maxsus endpoint'lar ─────────────
# Generic PUT /users/{id} ham ishlaydi, lekin alohida endpoint'lar:
#  • Idempotent (ikki marta bossa muammo emas)
#  • Notification ichkarida (frontend yoddan chiqarmaydi)
#  • Audit log qo'shish oson (kelajakda)
#  • REST semantics: action endpoint'lar
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{user_id}/verify", response_model=UserResponse)
def verify_user(
    user_id: int,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    """Haydovchini tasdiqlash. Idempotent."""
    user = db.query(User).options(joinedload(User.driver_profile)).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "Foydalanuvchi topilmadi")

    if user.is_verified and user.is_active:
        return user  # idempotent

    user.is_verified = True
    user.is_active = True  # rad etilgan bo'lsa qayta faollashtiramiz
    db.commit()
    db.refresh(user)

    # Telegram notification — fon vazifasida (tezkor javob qaytarish uchun)
    if user.role == UserRole.DRIVER and user.telegram_id:
        background.add_task(notify_driver_verified, user)

    return user


@router.post("/{user_id}/reject", response_model=UserResponse)
def reject_user(
    user_id: int,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    """Haydovchini rad etish (bloklash). is_active=False qilinadi."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "Foydalanuvchi topilmadi")

    user.is_active = False
    db.commit()
    db.refresh(user)

    if user.role == UserRole.DRIVER and user.telegram_id:
        background.add_task(notify_driver_rejected, user)

    return user


@router.post("/{user_id}/unblock", response_model=UserResponse)
def unblock_user(
    user_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    """Bloklangan foydalanuvchini qayta faollashtirish."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "Foydalanuvchi topilmadi")

    user.is_active = True
    db.commit()
    db.refresh(user)
    return user


# ─── Driver-specific endpoints ───────────────────────────────────────────────

@router.get("/drivers/available", response_model=list[UserResponse])
def available_drivers(db: Session = Depends(get_db), _=Depends(require_admin)):
    return (
        db.query(User)
        .join(DriverProfile)
        .options(joinedload(User.driver_profile))
        .filter(
            User.role == UserRole.DRIVER,
            User.is_active == True,
            User.is_verified == True,
            DriverProfile.is_available == True,
        )
        .all()
    )


@router.post("/{user_id}/driver-profile", response_model=DriverProfileResponse, status_code=201)
def create_driver_profile(
    user_id: int, body: DriverProfileCreate,
    db: Session = Depends(get_db), _=Depends(require_admin),
):
    """
    Admin tomondan haydovchi mashina ma'lumotlarini kiritish.
    Avtomatik is_verified=True qiladi (admin tasdiqlash bilan birga).
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "Foydalanuvchi topilmadi")
    if db.query(DriverProfile).filter(DriverProfile.user_id == user_id).first():
        raise HTTPException(400, "Haydovchi profili allaqachon mavjud")

    profile = DriverProfile(user_id=user_id, **body.model_dump())
    db.add(profile)
    user.role = UserRole.DRIVER
    user.is_verified = True
    user.is_active = True
    db.commit()
    db.refresh(profile)
    return profile


@router.put("/{user_id}/driver-profile", response_model=DriverProfileResponse)
def update_driver_profile(
    user_id: int, body: DriverProfileUpdate,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.ADMIN and current_user.id != user_id:
        raise HTTPException(403, "Ruxsat yo'q")
    profile = db.query(DriverProfile).filter(DriverProfile.user_id == user_id).first()
    if not profile:
        raise HTTPException(404, "Haydovchi profili topilmadi")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(profile, k, v)
    db.commit()
    db.refresh(profile)
    return profile
