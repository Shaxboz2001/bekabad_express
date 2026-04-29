"""
PATCH: TripCreate schema'sida pickup_lat/pickup_lng/pickup_address qo'shish
==========================================================================

XATO:
  AttributeError: 'TripCreate' object has no attribute 'pickup_lat'

SABAB:
  trips.py'da `body.pickup_lat` o'qiladi, lekin sizning Pydantic schema'ngizda
  bu field yo'q. Schema'ni yangilash kerak.

ECHIM:
  Sizning `app/schemas/trip.py` (yoki qayerda TripCreate yozilgan bo'lsa)
  ichida quyidagi o'zgarishlarni qiling.
"""

# ═══════════════════════════════════════════════════════════════════════════
# QADAM 1: Imports'ga qo'shing
# ═══════════════════════════════════════════════════════════════════════════
from typing import Optional
from pydantic import BaseModel, Field, model_validator


# ═══════════════════════════════════════════════════════════════════════════
# QADAM 2: TripBase yoki TripCreate class'iga 3 ta field qo'shing
# ═══════════════════════════════════════════════════════════════════════════
#
# AVVAL (sizning hozirgi kodingiz, taxminan):
#
#     class TripCreate(BaseModel):
#         direction: str
#         pickup_point: str
#         dropoff_point: str
#         trip_date: datetime
#         seats: int
#         category: str
#         car_type_preference: Optional[str] = 'any'
#         notes: Optional[str] = None
#         luggage: bool = False
#
#
# KEYIN (yangi):
#
#     class TripCreate(BaseModel):
#         direction: str
#         pickup_point: str
#         dropoff_point: str
#         trip_date: datetime
#         seats: int
#         category: str
#         car_type_preference: Optional[str] = 'any'
#         notes: Optional[str] = None
#         luggage: bool = False
#
#         # ▼▼▼ YANGI ▼▼▼
#         pickup_lat: Optional[float] = Field(None, ge=37.0, le=46.0)
#         pickup_lng: Optional[float] = Field(None, ge=55.0, le=74.0)
#         pickup_address: Optional[str] = Field(None, max_length=500)
#
#         @model_validator(mode='after')
#         def coords_paired(self):
#             if (self.pickup_lat is None) != (self.pickup_lng is None):
#                 raise ValueError(
#                     'pickup_lat va pickup_lng yo ikkalasi ham, yo hech qaysi'
#                 )
#             return self


# ═══════════════════════════════════════════════════════════════════════════
# QADAM 3: TripResponse'ga ham qo'shing (haydovchi xaritani ko'rishi uchun)
# ═══════════════════════════════════════════════════════════════════════════
#
#     class TripResponse(BaseModel):
#         id: int
#         direction: str
#         pickup_point: str
#         # ... boshqa field'lar ...
#
#         # ▼▼▼ YANGI ▼▼▼
#         pickup_lat: Optional[float] = None
#         pickup_lng: Optional[float] = None
#         pickup_address: Optional[str] = None
#
#         class Config:
#             from_attributes = True


# ═══════════════════════════════════════════════════════════════════════════
# QADAM 4: Trip SQLAlchemy modelda field'lar borligini tekshiring
# ═══════════════════════════════════════════════════════════════════════════
# Agar `app/models/trip.py`'da bu field'lar yo'q bo'lsa, ham xato bo'ladi
# (pickup_lat=... argument berib bo'lmaydi).
#
# Trip model'iga (app/models/trip.py) qo'shing:
#
#     from sqlalchemy import Column, Float, String
#
#     class Trip(Base):
#         __tablename__ = 'trips'
#         # ... mavjud field'lar ...
#
#         # ▼▼▼ YANGI ▼▼▼
#         pickup_lat = Column(Float, nullable=True)
#         pickup_lng = Column(Float, nullable=True)
#         pickup_address = Column(String(500), nullable=True)


# ═══════════════════════════════════════════════════════════════════════════
# QADAM 5: DB migration ishga tushiring
# ═══════════════════════════════════════════════════════════════════════════
#
#   psql -U postgres -d <db_name> < patches/001_add_location.sql
#
# YOKI Alembic'da:
#
#   alembic revision --autogenerate -m "add trip location fields"
#   alembic upgrade head


# ═══════════════════════════════════════════════════════════════════════════
# QADAM 6: Backend restart
# ═══════════════════════════════════════════════════════════════════════════
#
#   systemctl restart bekobod-backend
#   # yoki
#   sudo supervisorctl restart bekobod
#   # yoki
#   docker-compose restart backend


# ═══════════════════════════════════════════════════════════════════════════
# To'liq ishlovchi namuna (siz to'g'ridan-to'g'ri ishlatishingiz mumkin):
# ═══════════════════════════════════════════════════════════════════════════

from datetime import datetime


class TripBase(BaseModel):
    direction: str
    pickup_point: str = Field(..., min_length=2, max_length=500)
    dropoff_point: str = Field(..., min_length=2, max_length=500)
    trip_date: datetime
    seats: int = Field(..., ge=1, le=20)
    category: str
    car_type_preference: Optional[str] = 'any'
    notes: Optional[str] = Field(None, max_length=1000)
    luggage: bool = False

    # Location field'lari — barchasi optional, paired
    pickup_lat: Optional[float] = Field(None, ge=37.0, le=46.0)
    pickup_lng: Optional[float] = Field(None, ge=55.0, le=74.0)
    pickup_address: Optional[str] = Field(None, max_length=500)

    @model_validator(mode='after')
    def coords_paired(self):
        if (self.pickup_lat is None) != (self.pickup_lng is None):
            raise ValueError(
                'pickup_lat va pickup_lng yo ikkalasi ham, yo hech qaysi'
            )
        return self


class TripCreate(TripBase):
    pass
