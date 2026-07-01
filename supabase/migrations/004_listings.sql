CREATE TABLE listings (
  id                      uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  source                  text        NOT NULL CHECK (source IN ('property24', 'private_property', 'manual')),
  source_id               text,
  source_url              text,
  email_message_id        text,
  listing_type            text        NOT NULL CHECK (listing_type IN ('for_sale', 'to_let')),
  status                  text        NOT NULL DEFAULT 'active' CHECK (status IN (
                                        'active', 'sold', 'let', 'withdrawn', 'price_reduced'
                                      )),
  estate                  text,
  suburb                  text,
  area                    text,
  street                  text,
  street_number           text,
  unit                    text,
  sectional_scheme        text,
  property_type           text        CHECK (property_type IN ('freehold', 'sectional_title', 'vacant_land')),
  bedrooms                integer,
  bathrooms               integer,
  parking                 integer,
  erf_size_m2             integer,
  floor_size_m2           integer,
  has_pool                boolean     DEFAULT false,
  has_staff_accommodation boolean     DEFAULT false,
  pet_friendly            boolean     DEFAULT false,
  asking_price            bigint,
  monthly_rental          bigint,
  price_per_m2            integer,
  heading                 text,
  description             text,
  agent_name              text,
  agency                  text,
  listing_date            date,
  first_seen_at           timestamptz DEFAULT now(),
  last_seen_at            timestamptz DEFAULT now(),
  last_price_at           timestamptz,
  previous_price          bigint,
  created_at              timestamptz DEFAULT now(),
  updated_at              timestamptz DEFAULT now()
);

CREATE TABLE listing_price_history (
  id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  listing_id   uuid        REFERENCES listings(id) ON DELETE CASCADE,
  listing_type text        NOT NULL,
  old_price    bigint,
  new_price    bigint,
  changed_at   timestamptz DEFAULT now()
);

CREATE INDEX idx_listings_estate        ON listings (estate);
CREATE INDEX idx_listings_status        ON listings (status);
CREATE INDEX idx_listings_source        ON listings (source, source_id);
CREATE INDEX idx_listings_listing_type  ON listings (listing_type);

ALTER TABLE listings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "public read listings"
  ON listings FOR SELECT USING (true);
CREATE POLICY "public insert listings"
  ON listings FOR INSERT WITH CHECK (true);
CREATE POLICY "public update listings"
  ON listings FOR UPDATE USING (true);

ALTER TABLE listing_price_history ENABLE ROW LEVEL SECURITY;

CREATE POLICY "public read listing_price_history"
  ON listing_price_history FOR SELECT USING (true);
CREATE POLICY "public insert listing_price_history"
  ON listing_price_history FOR INSERT WITH CHECK (true);
