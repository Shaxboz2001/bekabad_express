from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_
from datetime import datetime, date
from typing import Optional
from app.db.session import get_db
from app.api.deps import get_current_user, require_admin, require_driver
from app.models.user import User, UserRole
from app.models.trip import Trip, TripStatus, TripDirection, TripCategory
from app.models.driver_profile import DriverProfile, Pricing
from app.schemas.trip import (
    TripCreate, TripUpdate, TripResponse, TripListResponse,
    TripStatusUpdate, AnalyticsResponse, PricingCreate, PricingUpdate, PricingResponse,
)
from app.services.telegram import (
    notify_trip_accepted, notify_trip_cancelled_passenger,
    notify_trip_cancelled_driver, notify_new_trip_to_drivers,
    notify_trip_completed,
)

router = APIRouter(prefix="/trips", tags=["trips"])


def _load(db, trip_id) -> Optional[Trip]:
    return db.query(Trip).options(
        joinedload(Trip.passenger),
        joinedload(Trip.driver).joinedload(User.driver_profile),
    ).filter(Trip.id == trip_id).first()


# ─── Pricing ─────────────────────────────────────────────────────────────────
@router.get("/pricing", response_model=list[PricingResponse])
def get_pricing(db: Session = Depends(get_db)):
    return db.query(Pricing).filter(Pricing.is_active == True).all()


@router.post("/pricing", response_model=PricingResponse, status_code=201)
def create_pricing(body: PricingCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    existing = db.query(Pricing).filter(
        Pricing.direction == body.direction,
        Pricing.category == body.category,
    ).first()
    if existing:
        existing.price_per_seat = body.price_per_seat
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return existing

    p = Pricing(**body.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.put("/pricing/{pricing_id}", response_model=PricingResponse)
def update_pricing(pricing_id: int, body: PricingUpdate, db: Session = Depends(get_db), _=Depends(require_admin)):
    p = db.query(Pricing).filter(Pricing.id == pricing_id).first()
    if not p:
        raise HTTPException(404, "Narx topilmadi")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    return p


# ─── Create Trip ─────────────────────────────────────────────────────────────
@router.post("/", response_model=TripResponse, status_code=201)
async def create_trip(
    body: TripCreate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.PASSENGER:
        raise HTTPException(403, "Faqat yo'lovchilar e'lon bera oladi")

    pricing = db.query(Pricing).filter(
        Pricing.direction == body.direction,
        Pricing.category == body.category,
        Pricing.is_active == True,
    ).first()
    if not pricing:
        raise HTTPException(400, "Bu yo'nalish uchun narx belgilanmagan. Admin bilan bog'laning.")

    total = pricing.price_per_seat * body.seats

    trip = Trip(
        passenger_id=current_user.id,
        direction=body.direction,
        pickup_point=body.pickup_point,
        dropoff_point=body.dropoff_point,
        trip_date=body.trip_date,
        seats=body.seats,
        category=body.category,
        car_type_preference=body.car_type_preference,
        notes=body.notes,
        luggage=body.luggage,
        price_per_seat=pricing.price_per_seat,
        total_price=total,
        status=TripStatus.ACTIVE,
        # ─── Location (yangi, ixtiyoriy) ──────────────────────────────────
        # `getattr` ishlatamiz — schema hali yangilanmagan bo'lsa AttributeError
        # bo'lmaydi. Schema yangilangach to'g'ridan-to'g'ri body.pickup_lat ham
        # ishlaydi. Trip model'da bu field'lar bo'lmasa, bu argumentlarni
        # commentga oling yoki Trip model'iga avval field qo'shing.
        pickup_lat=getattr(body, 'pickup_lat', None),
        pickup_lng=getattr(body, 'pickup_lng', None),
        pickup_address=getattr(body, 'pickup_address', None),
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)

    # Tasdiqlangan, faol haydovchilarga xabar
    # Eslatma: Bu join driver_profile bo'lmagan haydovchilarni filtrlaydi.
    # Demak admin tasdiqlagan-u, mashina ma'lumotlari kiritilmagan haydovchilar
    # xabar olmaydi (bu xohlangan xulq).
    drivers = db.query(User).join(DriverProfile).filter(
        User.role == UserRole.DRIVER,
        User.is_active == True,
        User.is_verified == True,
        DriverProfile.is_available == True,
        User.telegram_id.isnot(None),
    ).all()
    driver_tg_ids = [d.telegram_id for d in drivers if d.telegram_id]

    result = _load(db, trip.id)
    background.add_task(notify_new_trip_to_drivers, result, driver_tg_ids)

    return result


# ─── List Trips ──────────────────────────────────────────────────────────────
@router.get("/", response_model=TripListResponse)
def list_trips(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    direction: Optional[TripDirection] = None,
    category: Optional[TripCategory] = None,
    status: Optional[TripStatus] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Trip).options(
        joinedload(Trip.passenger),
        joinedload(Trip.driver).joinedload(User.driver_profile),
    )

    # Role-based filtering
    if current_user.role == UserRole.PASSENGER:
        q = q.filter(Trip.passenger_id == current_user.id)
    elif current_user.role == UserRole.DRIVER:
        q = q.filter(or_(
            Trip.driver_id == current_user.id,
            Trip.status == TripStatus.ACTIVE,
        ))
    # Admin: hammasi (filter qo'shilmaydi)

    if direction:
        q = q.filter(Trip.direction == direction)
    if category:
        q = q.filter(Trip.category == category)
    if status:
        q = q.filter(Trip.status == status)
    if date_from:
        q = q.filter(Trip.trip_date >= datetime.fromisoformat(date_from))
    if date_to:
        q = q.filter(Trip.trip_date <= datetime.fromisoformat(date_to))

    q = q.order_by(Trip.trip_date.asc(), Trip.created_at.desc())
    total = q.count()
    items = q.offset((page - 1) * size).limit(size).all()

    return TripListResponse(
        items=items, total=total, page=page, size=size,
        pages=(total + size - 1) // size,
    )


# ─── Active trips for drivers ────────────────────────────────────────────────
@router.get("/active", response_model=TripListResponse)
def active_trips_for_drivers(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    direction: Optional[TripDirection] = None,
    category: Optional[TripCategory] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_driver),
):
    """Haydovchilar uchun: qabul qilish mumkin bo'lgan faol e'lonlar"""
    q = db.query(Trip).options(
        joinedload(Trip.passenger),
    ).filter(
        Trip.status == TripStatus.ACTIVE,
        Trip.trip_date > datetime.utcnow(),
    )
    if direction:
        q = q.filter(Trip.direction == direction)
    if category:
        q = q.filter(Trip.category == category)

    q = q.order_by(Trip.trip_date.asc())
    total = q.count()
    items = q.offset((page - 1) * size).limit(size).all()

    return TripListResponse(
        items=items, total=total, page=page, size=size,
        pages=(total + size - 1) // size,
    )


# ─── Get single trip ─────────────────────────────────────────────────────────
@router.get("/{trip_id}", response_model=TripResponse)
def get_trip(trip_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    trip = _load(db, trip_id)
    if not trip:
        raise HTTPException(404, "E'lon topilmadi")

    if current_user.role == UserRole.PASSENGER and trip.passenger_id != current_user.id:
        raise HTTPException(403, "Ruxsat yo'q")

    return trip


# ─── Driver accepts trip ─────────────────────────────────────────────────────
@router.post("/{trip_id}/accept", response_model=TripResponse)
async def accept_trip(
    trip_id: int,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_driver),
):
    # Status check'ni atomic qilish uchun row-level lock
    # Aks holda ikki haydovchi bir vaqtda accept qilsa, ikkalasi ham success oladi
    trip = db.query(Trip).filter(Trip.id == trip_id).with_for_update().first()
    if not trip:
        raise HTTPException(404, "E'lon topilmadi")
    if trip.status != TripStatus.ACTIVE:
        raise HTTPException(400, "Bu e'lon allaqachon qabul qilingan yoki bekor qilingan")
    if trip.passenger_id == current_user.id:
        raise HTTPException(400, "O'z e'loningizni qabul qila olmaysiz")

    profile = db.query(DriverProfile).filter(DriverProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(
            400,
            "Mashina ma'lumotlari kiritilmagan. Admin bilan bog'laning: @bekobod_admin",
        )

    trip.driver_id = current_user.id
    trip.status = TripStatus.ACCEPTED
    trip.accepted_at = datetime.utcnow()
    db.commit()

    result = _load(db, trip.id)
    background.add_task(notify_trip_accepted, result)

    return result


# ─── Update trip status ──────────────────────────────────────────────────────
@router.patch("/{trip_id}/status", response_model=TripResponse)
async def update_status(
    trip_id: int,
    body: TripStatusUpdate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(404, "E'lon topilmadi")

    # Permission checks
    if current_user.role == UserRole.PASSENGER:
        if trip.passenger_id != current_user.id:
            raise HTTPException(403, "Ruxsat yo'q")
        if body.status not in [TripStatus.CANCELLED]:
            raise HTTPException(403, "Foydalanuvchi faqat bekor qila oladi")
    elif current_user.role == UserRole.DRIVER:
        if trip.driver_id != current_user.id:
            raise HTTPException(403, "Ruxsat yo'q")
        if body.status not in [TripStatus.IN_PROGRESS, TripStatus.COMPLETED, TripStatus.CANCELLED]:
            raise HTTPException(403, "Noto'g'ri status")
    # Admin har qanday holatga o'zgartira oladi

    trip.status = body.status
    if body.cancellation_reason:
        trip.cancellation_reason = body.cancellation_reason
    if body.status == TripStatus.COMPLETED:
        trip.completed_at = datetime.utcnow()
        if trip.driver_id:
            profile = db.query(DriverProfile).filter(DriverProfile.user_id == trip.driver_id).first()
            if profile:
                profile.total_trips += 1
    db.commit()

    result = _load(db, trip_id)

    if body.status == TripStatus.CANCELLED:
        background.add_task(notify_trip_cancelled_passenger, result, body.cancellation_reason or "")
        if result.driver_id:
            background.add_task(notify_trip_cancelled_driver, result, body.cancellation_reason or "")
    elif body.status == TripStatus.COMPLETED:
        background.add_task(notify_trip_completed, result)

    return result


# ─── Analytics ───────────────────────────────────────────────────────────────
@router.get("/admin/analytics", response_model=AnalyticsResponse)
def get_analytics(db: Session = Depends(get_db), _=Depends(require_admin)):
    today_start = datetime.combine(date.today(), datetime.min.time())

    total = db.query(func.count(Trip.id)).scalar()
    active = db.query(func.count(Trip.id)).filter(Trip.status == TripStatus.ACTIVE).scalar()
    completed = db.query(func.count(Trip.id)).filter(Trip.status == TripStatus.COMPLETED).scalar()
    cancelled = db.query(func.count(Trip.id)).filter(Trip.status == TripStatus.CANCELLED).scalar()
    passengers = db.query(func.count(User.id)).filter(User.role == UserRole.PASSENGER).scalar()
    total_drivers = db.query(func.count(User.id)).filter(User.role == UserRole.DRIVER).scalar()
    active_drivers = db.query(func.count(DriverProfile.id)).filter(DriverProfile.is_available == True).scalar()
    trips_today = db.query(func.count(Trip.id)).filter(Trip.created_at >= today_start).scalar()
    revenue = db.query(func.coalesce(func.sum(Trip.total_price), 0)).filter(Trip.status == TripStatus.COMPLETED).scalar()
    revenue_today = db.query(func.coalesce(func.sum(Trip.total_price), 0)).filter(
        and_(Trip.status == TripStatus.COMPLETED, Trip.completed_at >= today_start)
    ).scalar()
    b2t = db.query(func.count(Trip.id)).filter(Trip.direction == TripDirection.BEKOBOD_TO_TASHKENT).scalar()
    t2b = db.query(func.count(Trip.id)).filter(Trip.direction == TripDirection.TASHKENT_TO_BEKOBOD).scalar()

    return AnalyticsResponse(
        total_trips=total, active_trips=active, completed_trips=completed,
        cancelled_trips=cancelled, total_passengers=passengers,
        total_drivers=total_drivers, active_drivers=active_drivers,
        trips_today=trips_today, total_revenue=float(revenue),
        revenue_today=float(revenue_today),
        bekobod_to_tashkent=b2t, tashkent_to_bekobod=t2b,
    )
