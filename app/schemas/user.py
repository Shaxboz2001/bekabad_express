from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime
from app.models.user import UserRole
from app.models.trip import CarType


# ─── Driver profile ──────────────────────────────────────────────────────────
class DriverProfileResponse(BaseModel):
    id: int
    user_id: int
    car_model: str
    car_number: str
    car_color: Optional[str]
    car_type: CarType
    car_year: Optional[int]
    seats_available: int
    is_available: bool
    rating: float
    total_trips: int
    model_config = {"from_attributes": True}


class DriverProfileCreate(BaseModel):
    car_model: str
    car_number: str
    car_color: Optional[str] = None
    car_type: CarType = CarType.SEDAN
    car_year: Optional[int] = None
    license_number: str
    seats_available: int = 4

    @field_validator("car_model", "car_number", "license_number")
    @classmethod
    def non_empty(cls, v: str) -> str:
        v = (v or "").strip()
        if len(v) < 2:
            raise ValueError("Maydon kamida 2 belgidan iborat bo'lishi kerak")
        return v

    @field_validator("seats_available")
    @classmethod
    def validate_seats(cls, v: int) -> int:
        if v < 1 or v > 20:
            raise ValueError("Joylar 1-20 oralig'ida bo'lishi kerak")
        return v


class DriverProfileUpdate(BaseModel):
    car_model: Optional[str] = None
    car_number: Optional[str] = None
    car_color: Optional[str] = None
    car_type: Optional[CarType] = None
    seats_available: Optional[int] = None
    is_available: Optional[bool] = None


# ─── User ────────────────────────────────────────────────────────────────────
class UserResponse(BaseModel):
    id: int
    telegram_id: Optional[int]
    full_name: str
    phone: str
    username: Optional[str]
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime
    driver_profile: Optional[DriverProfileResponse] = None
    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    full_name: str
    phone: str
    password: str
    role: UserRole = UserRole.PASSENGER


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None


# ─── Auth ────────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    phone: str
    password: str


class TelegramAuthRequest(BaseModel):
    """
    Telegram orqali kirish/ro'yxatdan o'tish.

    Foydalanish stsenariylari:
      1. Login (mavjud user) — faqat telegram_id va full_name kerak
      2. Yangi yo'lovchi — + role="passenger" + phone (ixtiyoriy lekin tavsiya etiladi)
      3. Yangi haydovchi — + role="driver" + phone + driver_profile (mashina ma'lumotlari)
    """
    telegram_id: int
    full_name: str
    username: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None  # "driver" | "passenger"

    # Driver registratsiya paytida — atomik yaratish uchun
    driver_profile: Optional[DriverProfileCreate] = None

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return v
        v = v.strip().replace(" ", "").replace("-", "").replace("+", "")
        if not v:
            return None
        # 998901234567 yoki 901234567 → 998901234567
        if v.startswith("998"):
            pass
        elif len(v) == 9 and v.isdigit():
            v = "998" + v
        if not v.isdigit() or len(v) != 12 or not v.startswith("998"):
            raise ValueError("Telefon raqami 998XXXXXXXXX shaklida bo'lishi kerak")
        return v


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class RefreshRequest(BaseModel):
    refresh_token: str
