-- ─── Migration: add location fields to trips table ──────────────────────────
-- Bu SQL'ni Alembic migration sifatida yoki to'g'ridan-to'g'ri DB'ga ishlating.
--
-- Yangi field'lar:
--   • pickup_lat        — yo'lovchi belgilagan lat (NULL bo'lishi mumkin)
--   • pickup_lng        — yo'lovchi belgilagan lng (NULL bo'lishi mumkin)
--   • pickup_address    — reverse geocoding'dan olingan manzil (NULL bo'lishi mumkin)
--
-- Eski trip'lar uchun NULL bo'ladi — backward compatible.

ALTER TABLE trips
  ADD COLUMN IF NOT EXISTS pickup_lat       DOUBLE PRECISION NULL,
  ADD COLUMN IF NOT EXISTS pickup_lng       DOUBLE PRECISION NULL,
  ADD COLUMN IF NOT EXISTS pickup_address   VARCHAR(500)     NULL;

-- Geo bo'yicha qidiruv tezligi uchun BRIN index (kichik joy talab qiladi).
-- Agar geo radius search kerak bo'lsa, GIST + ll_to_earth() ishlatish kerak,
-- lekin hozirgi MVP'da kerak emas.
CREATE INDEX IF NOT EXISTS ix_trips_pickup_coords
  ON trips (pickup_lat, pickup_lng)
  WHERE pickup_lat IS NOT NULL;

-- Constraint: ikkala koordinata birga bo'lishi yoki ikkala ham NULL
ALTER TABLE trips
  ADD CONSTRAINT chk_trips_pickup_coords_paired
  CHECK (
    (pickup_lat IS NULL AND pickup_lng IS NULL) OR
    (pickup_lat IS NOT NULL AND pickup_lng IS NOT NULL)
  );

-- O'zbekiston hududi cheklovi (xato kiritishni oldini olish)
ALTER TABLE trips
  ADD CONSTRAINT chk_trips_pickup_lat_range
  CHECK (pickup_lat IS NULL OR (pickup_lat BETWEEN 37.0 AND 46.0));

ALTER TABLE trips
  ADD CONSTRAINT chk_trips_pickup_lng_range
  CHECK (pickup_lng IS NULL OR (pickup_lng BETWEEN 55.0 AND 74.0));
