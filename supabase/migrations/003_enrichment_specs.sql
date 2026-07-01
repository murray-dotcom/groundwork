-- Adds extended enrichment columns to property_attributes
ALTER TABLE property_attributes
  ADD COLUMN IF NOT EXISTS bedrooms               integer,
  ADD COLUMN IF NOT EXISTS bathrooms              integer,
  ADD COLUMN IF NOT EXISTS has_pool               boolean DEFAULT false,
  ADD COLUMN IF NOT EXISTS has_staff_accommodation boolean DEFAULT false,
  ADD COLUMN IF NOT EXISTS has_stairs             boolean DEFAULT false;
