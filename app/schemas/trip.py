# backend/app/schemas/trip.py

from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import datetime, timezone
from app.models.trip import TripDirection, TripCategory, TripStatus, CarType
from app.schemas.user import UserResponse, DriverProfileResponse


class TripCreate(BaseModel):
    direction: TripDirection
    pickup_point: str
    dropoff_point: str
    trip_date: datetime
    seats: int = 1
    category: TripCategory = TripCategory.PASSENGER
    car_type_preference: CarType = CarType.ANY
    notes: Optional[str] = None
    luggage: bool = False

    @field_validator("seats")
    @classmethod
    def validate_seats(cls, v):
        if v < 1 or v > 8:
            raise ValueError("Joy soni 1 dan 8 gacha bo'lishi kerak")
        return v

    @field_validator("trip_date")
    @classmethod
    def validate_date(cls, v):
        # timezone-aware qilib solishtirish
        now = datetime.now(timezone.utc)
        if v.tzinfo is None:
            # frontend timezone bermagan bo'lsa — UTC deb qabul qilamiz
            v = v.replace(tzinfo=timezone.utc)
        if v < now:
            raise ValueError("O'tib ketgan sana kiritib bo'lmaydi")
        return v


class TripUpdate(BaseModel):
    notes: Optional[str] = None
    luggage: Optional[bool] = None


class TripStatusUpdate(BaseModel):
    status: TripStatus
    cancellation_reason: Optional[str] = None


class DriverInfo(BaseModel):
    id: int
    full_name: str
    phone: str
    driver_profile: Optional[DriverProfileResponse] = None

    model_config = {"from_attributes": True}


class TripResponse(BaseModel):
    id: int
    passenger_id: int
    driver_id: Optional[int]
    direction: TripDirection
    pickup_point: str
    dropoff_point: str
    trip_date: datetime
    seats: int
    category: TripCategory
    car_type_preference: CarType
    price_per_seat: float
    total_price: float
    notes: Optional[str]
    luggage: bool
    status: TripStatus
    cancellation_reason: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    accepted_at: Optional[datetime]
    completed_at: Optional[datetime]
    passenger: Optional[UserResponse] = None
    driver: Optional[DriverInfo] = None

    model_config = {"from_attributes": True}


class TripListResponse(BaseModel):
    items: List[TripResponse]
    total: int
    page: int
    size: int
    pages: int


# ─── Pricing ──────────────────────────────────────────────────────────────────
class PricingCreate(BaseModel):
    direction: TripDirection
    category: TripCategory
    price_per_seat: float


class PricingUpdate(BaseModel):
    price_per_seat: float
    is_active: Optional[bool] = None


class PricingResponse(BaseModel):
    id: int
    direction: TripDirection
    category: TripCategory
    price_per_seat: float
    is_active: bool

    model_config = {"from_attributes": True}


# ─── Analytics ────────────────────────────────────────────────────────────────
class AnalyticsResponse(BaseModel):
    total_trips: int
    active_trips: int
    completed_trips: int
    cancelled_trips: int
    total_passengers: int
    total_drivers: int
    active_drivers: int
    trips_today: int
    total_revenue: float
    revenue_today: float
    bekobod_to_tashkent: int
    tashkent_to_bekobod: int