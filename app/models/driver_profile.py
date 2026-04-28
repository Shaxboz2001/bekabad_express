from sqlalchemy import (
    Column, Integer, String, Float, Boolean,
    ForeignKey, DateTime, Enum as SAEnum, func
)
from sqlalchemy.orm import relationship
from app.db.session import Base
from app.models.trip import TripDirection, CarType, TripCategory


def enum_values(enum_cls):
    return [e.value for e in enum_cls]


class DriverProfile(Base):
    __tablename__ = "driver_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)

    car_model = Column(String(100), nullable=False)
    car_number = Column(String(20), nullable=False)
    car_color = Column(String(50), nullable=True)

    car_type = Column(
        SAEnum(CarType, name="cartype", values_callable=enum_values),
        default=CarType.SEDAN,
        nullable=False,
    )

    car_year = Column(Integer, nullable=True)
    license_number = Column(String(50), nullable=False)
    seats_available = Column(Integer, default=4)

    is_available = Column(Boolean, default=True)
    rating = Column(Float, default=5.0)
    total_trips = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="driver_profile")


class Pricing(Base):
    __tablename__ = "pricing"

    id = Column(Integer, primary_key=True, index=True)

    direction = Column(
        SAEnum(TripDirection, name="tripdirection", values_callable=enum_values),
        nullable=False,
    )

    category = Column(
        SAEnum(TripCategory, name="tripcategory", values_callable=enum_values),
        nullable=False,
    )

    price_per_seat = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())