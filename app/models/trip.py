import enum
from sqlalchemy import (
    Column, Integer, String, Float, ForeignKey,
    Enum as SAEnum, DateTime, Text, Boolean, func
)
from sqlalchemy.orm import relationship
from app.db.session import Base


def enum_values(enum_cls):
    return [e.value for e in enum_cls]


class TripDirection(str, enum.Enum):
    BEKOBOD_TO_TASHKENT = "bekobod_to_tashkent"
    TASHKENT_TO_BEKOBOD = "tashkent_to_bekobod"


class TripCategory(str, enum.Enum):
    PASSENGER = "passenger"
    PASSENGER_SMALL_CARGO = "passenger_small_cargo"
    CARGO = "cargo"


class TripStatus(str, enum.Enum):
    ACTIVE = "active"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class CarType(str, enum.Enum):
    ANY = "any"
    SEDAN = "sedan"
    MINIVAN = "minivan"
    CARGO_VAN = "cargo_van"


class Trip(Base):
    __tablename__ = "trips"

    id = Column(Integer, primary_key=True, index=True)

    passenger_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    driver_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    direction = Column(
        SAEnum(TripDirection, name="tripdirection", values_callable=enum_values),
        nullable=False,
    )

    pickup_point = Column(String(300), nullable=False)
    dropoff_point = Column(String(300), nullable=False)

    trip_date = Column(DateTime(timezone=True), nullable=False)

    seats = Column(Integer, default=1, nullable=False)

    category = Column(
        SAEnum(TripCategory, name="tripcategory", values_callable=enum_values),
        default=TripCategory.PASSENGER,
        nullable=False,
    )

    car_type_preference = Column(
        SAEnum(CarType, name="cartype", values_callable=enum_values),
        default=CarType.ANY,
        nullable=False,
    )

    price_per_seat = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)

    notes = Column(Text, nullable=True)
    luggage = Column(Boolean, default=False)

    status = Column(
        SAEnum(TripStatus, name="tripstatus", values_callable=enum_values),
        default=TripStatus.ACTIVE,
        nullable=False,
    )

    cancellation_reason = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    passenger = relationship(
        "User",
        foreign_keys=[passenger_id],
        back_populates="trips_as_passenger",
    )

    driver = relationship(
        "User",
        foreign_keys=[driver_id],
        back_populates="trips_as_driver",
    )