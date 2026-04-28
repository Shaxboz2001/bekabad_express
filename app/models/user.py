import enum
from sqlalchemy import Column, Integer, String, Boolean, Enum as SAEnum, DateTime, BigInteger, func
from sqlalchemy.orm import relationship
from app.db.session import Base


def enum_values(enum_cls):
    return [e.value for e in enum_cls]


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    DRIVER = "driver"
    PASSENGER = "passenger"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=True)
    full_name = Column(String(150), nullable=False)
    phone = Column(String(20), unique=True, index=True, nullable=False)
    username = Column(String(100), nullable=True)
    hashed_password = Column(String(255), nullable=True)

    role = Column(
        SAEnum(UserRole, name="userrole", values_callable=enum_values),
        default=UserRole.PASSENGER,
        nullable=False,
    )

    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    trips_as_passenger = relationship(
        "Trip",
        foreign_keys="Trip.passenger_id",
        back_populates="passenger",
    )
    trips_as_driver = relationship(
        "Trip",
        foreign_keys="Trip.driver_id",
        back_populates="driver",
    )
    driver_profile = relationship(
        "DriverProfile",
        back_populates="user",
        uselist=False,
    )