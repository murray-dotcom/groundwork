CREATE TABLE property_attributes (
  id                   uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  title_deed_no        text        NOT NULL,
  estate               text        NOT NULL,
  built_area_m2        integer,
  sea_view             boolean     DEFAULT false,
  view_rating          integer     CHECK (view_rating BETWEEN 1 AND 5),
  property_detail_type text        CHECK (property_detail_type IN (
                                     'house', 'townhouse', 'apartment', 'vacant_land',
                                     'penthouse', 'duplex', 'simplex'
                                   )),
  condition_rating     integer     CHECK (condition_rating BETWEEN 1 AND 5),
  notes                text,
  created_at           timestamptz DEFAULT now(),
  updated_at           timestamptz DEFAULT now(),
  UNIQUE (title_deed_no, estate)
);

-- RLS
ALTER TABLE property_attributes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "public read property_attributes"
ON property_attributes FOR SELECT USING (true);

CREATE POLICY "public insert property_attributes"
ON property_attributes FOR INSERT WITH CHECK (true);

CREATE POLICY "public update property_attributes"
ON property_attributes FOR UPDATE USING (true);

-- Index for fast lookup by deed
CREATE INDEX idx_property_attributes_deed
ON property_attributes (title_deed_no, estate);
