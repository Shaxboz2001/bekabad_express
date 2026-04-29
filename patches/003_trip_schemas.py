"""
Trip schemas — location field'lari bilan kengaytirilgan.

Sizning mavjud `app/schemas/trip.py` ichida quyidagi o'zgarishlarni qiling:

1. TripBase / TripCreate / TripResponse — pickup_lat, pickup_lng, pickup_address qo'shing
2. Validator: agar bittasi berilsa, ikkalasi ham bo'lishi shart
3. O'zbekiston bbox tekshirish

Pastda to'liq namuna kod.
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, model_validator


# O'zbekiston bbox (extra security layer Pydantic'da)
UZ_LAT_MIN, UZ_LAT_MAX = 37.0, 46.0
UZ_LNG_MIN, UZ_LNG_MAX = 55.0, 74.0


class TripBase(BaseModel):
    direction: str  # 'bekobod_to_tashkent' | 'tashkent_to_bekobod'
    pickup_point: str = Field(..., min_length=2, max_length=500)
    dropoff_point: str = Field(..., min_length=2, max_length=500)
    trip_date: datetime
    seats: int = Field(..., ge=1, le=20)
    category: str  # 'passenger' | 'passenger_small_cargo' | 'cargo'
    car_type_preference: Optional[str] = 'any'
    notes: Optional[str] = Field(None, max_length=1000)
    luggage: bool = False

    # ─── Location fields (YANGI) ────────────────────────────────────────────
    pickup_lat: Optional[float] = Field(
        None, ge=UZ_LAT_MIN, le=UZ_LAT_MAX,
        description="Yo'lovchi belgilagan koordinata (latitude)",
    )
    pickup_lng: Optional[float] = Field(
        None, ge=UZ_LNG_MIN, le=UZ_LNG_MAX,
        description="Yo'lovchi belgilagan koordinata (longitude)",
    )
    pickup_address: Optional[str] = Field(
        None, max_length=500,
        description="Reverse geocoding orqali olingan manzil (opsional)",
    )

    @model_validator(mode='after')
    def coords_paired(self):
        """lat va lng birga bo'lishi yoki ikkalasi ham None"""
        if (self.pickup_lat is None) != (self.pickup_lng is None):
            raise ValueError(
                "pickup_lat va pickup_lng — yo ikkalasi ham, yo hech qaysi"
            )
        return self


class TripCreate(TripBase):
    """Yangi trip yaratish uchun (POST /api/v1/trips)."""
    pass


class TripUpdate(BaseModel):
    """Statusni o'zgartirish uchun (PATCH /api/v1/trips/{id})."""
    status: Optional[str] = None
    cancellation_reason: Optional[str] = Field(None, max_length=500)


class UserMini(BaseModel):
    """Trip ichida embed bo'lgan user info."""
    id: int
    full_name: str
    phone: Optional[str] = None
    username: Optional[str] = None
    telegram_id: Optional[int] = None

    class Config:
        from_attributes = True


class DriverProfileMini(BaseModel):
    car_model: str
    car_number: str
    car_color: Optional[str] = None
    car_year: Optional[int] = None
    car_type: str
    seats_available: int
    rating: float = 5.0
    total_trips: int = 0

    class Config:
        from_attributes = True


class DriverWithProfile(UserMini):
    driver_profile: Optional[DriverProfileMini] = None


class TripResponse(TripBase):
    id: int
    passenger_id: int
    driver_id: Optional[int] = None
    status: str
    price_per_seat: float
    total_price: float
    cancellation_reason: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    # Embed qilingan user'lar — frontend kontaktni ko'rsatishi uchun
    passenger: Optional[UserMini] = None
    driver: Optional[DriverWithProfile] = None

    class Config:
        from_attributes = True


class TripListResponse(BaseModel):
    items: List[TripResponse]
    total: int
    page: int
    size: int
