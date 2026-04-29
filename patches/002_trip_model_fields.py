# ─── Trip model'ga qo'shiladigan field'lar ───────────────────────────────────
# Bu fayl namuna sifatida — sizning `app/models/trip.py` ichidagi
# `class Trip(Base)` ga quyidagi field'larni qo'shing.

from sqlalchemy import Column, Float, String, CheckConstraint, Index

# class Trip(Base) ichiga qo'shing:

pickup_lat = Column(Float, nullable=True)
pickup_lng = Column(Float, nullable=True)
pickup_address = Column(String(500), nullable=True)

# __table_args__ ichiga qo'shing (yoki yangi yarating):
__table_args__ = (
    CheckConstraint(
        '(pickup_lat IS NULL AND pickup_lng IS NULL) OR '
        '(pickup_lat IS NOT NULL AND pickup_lng IS NOT NULL)',
        name='chk_trips_pickup_coords_paired'
    ),
    CheckConstraint(
        'pickup_lat IS NULL OR (pickup_lat BETWEEN 37.0 AND 46.0)',
        name='chk_trips_pickup_lat_range'
    ),
    CheckConstraint(
        'pickup_lng IS NULL OR (pickup_lng BETWEEN 55.0 AND 74.0)',
        name='chk_trips_pickup_lng_range'
    ),
    Index(
        'ix_trips_pickup_coords',
        'pickup_lat', 'pickup_lng',
        postgresql_where=(pickup_lat.isnot(None))
    ),
)
