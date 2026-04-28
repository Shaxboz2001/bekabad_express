"""
python seed.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.models.driver_profile import DriverProfile, Pricing
from app.models.trip import TripDirection, TripCategory, CarType
from app.core.security import get_password_hash


def seed():
    db = SessionLocal()

    try:
        if not db.query(User).filter(User.phone == "998333977646").first():
            admin2 = User(
                full_name="admin",
                phone="998333977646",
                telegram_id=1661832397,
                username="IsmoilovShaxboz",
                hashed_password=get_password_hash("admin123"),
                role=UserRole.ADMIN,
                is_active=True,
                is_verified=True,
            )
            db.add(admin2)
            db.flush()
            print("✅ Admin 2: 998333977646 / admin123")

        default_prices = [
            (TripDirection.BEKOBOD_TO_TASHKENT, TripCategory.PASSENGER, 50_000),
            (TripDirection.BEKOBOD_TO_TASHKENT, TripCategory.PASSENGER_SMALL_CARGO, 60_000),
            (TripDirection.BEKOBOD_TO_TASHKENT, TripCategory.CARGO, 150_000),
            (TripDirection.TASHKENT_TO_BEKOBOD, TripCategory.PASSENGER, 50_000),
            (TripDirection.TASHKENT_TO_BEKOBOD, TripCategory.PASSENGER_SMALL_CARGO, 60_000),
            (TripDirection.TASHKENT_TO_BEKOBOD, TripCategory.CARGO, 150_000),
        ]

        for direction, category, price in default_prices:
            exists = db.query(Pricing).filter(
                Pricing.direction == direction,
                Pricing.category == category,
            ).first()

            if not exists:
                db.add(
                    Pricing(
                        direction=direction,
                        category=category,
                        price_per_seat=price,
                    )
                )

        print("✅ Narxlar sozlandi")


        db.commit()

        print("\n🚀 Seed muvaffaqiyatli bajarildi!")
        print("\nDemo kirish:")
        print("  Admin:     998901234567 / admin123")
        print("  Haydovchi: 998901111111 / driver123")
        print("  Yo'lovchi: 998903333333 / user123")

    except Exception as e:
        db.rollback()
        print(f"❌ Xato: {e}")
        raise

    finally:
        db.close()


if __name__ == "__main__":
    seed()