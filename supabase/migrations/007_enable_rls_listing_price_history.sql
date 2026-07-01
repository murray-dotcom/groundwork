-- Applied directly in Supabase via Cowork (migration name: fix_enable_rls_on_listing_price_history).
-- listing_price_history RLS was enabled in the live DB but absent from 004_listings.sql at the time.
-- This migration is a no-op if 004_listings.sql already ran with RLS enabled.
ALTER TABLE listing_price_history ENABLE ROW LEVEL SECURITY;
