CREATE TABLE listing_sale_matches (
  id                    uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  listing_id            uuid        REFERENCES listings(id) ON DELETE CASCADE,
  transaction_id        uuid        REFERENCES transactions(id) ON DELETE CASCADE,
  price_difference_pct  numeric,
  status                text        NOT NULL DEFAULT 'pending_review' CHECK (status IN (
                                      'pending_review', 'confirmed', 'rejected'
                                    )),
  created_at            timestamptz DEFAULT now(),
  reviewed_at           timestamptz,
  UNIQUE (listing_id, transaction_id)
);

CREATE INDEX idx_listing_sale_matches_status
  ON listing_sale_matches (status);

ALTER TABLE listing_sale_matches ENABLE ROW LEVEL SECURITY;

CREATE POLICY "public read listing_sale_matches"
  ON listing_sale_matches FOR SELECT USING (true);
CREATE POLICY "public insert listing_sale_matches"
  ON listing_sale_matches FOR INSERT WITH CHECK (true);
CREATE POLICY "public update listing_sale_matches"
  ON listing_sale_matches FOR UPDATE USING (true);

-- Add columns to listings for enrichment and sale linkage
ALTER TABLE listings
  ADD COLUMN IF NOT EXISTS sold_transaction_id   uuid        REFERENCES transactions(id),
  ADD COLUMN IF NOT EXISTS full_description      text,
  ADD COLUMN IF NOT EXISTS enriched_at           timestamptz,
  ADD COLUMN IF NOT EXISTS needs_estate_review   boolean     DEFAULT false;
