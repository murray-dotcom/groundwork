-- Codifies live RLS state on transactions/import_log (previously applied via Cowork,
-- never captured in the repo) and removes public write policies from tables that are
-- only ever written server-side (service role bypasses RLS, so agents are unaffected).
--
-- DELIBERATELY UNCHANGED: property_attributes keeps public insert/update because the
-- CMA app's enrichment panel writes to it from the browser with the anon key. This is
-- a documented residual risk. Follow-up: proxy those writes through a Netlify function
-- using the service role, then drop these two policies.

-- Codify live state (idempotent):
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE import_log   ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public'
                 AND tablename='transactions' AND policyname='public read transactions') THEN
    CREATE POLICY "public read transactions" ON transactions FOR SELECT USING (true);
  END IF;
END $$;
-- import_log intentionally has NO policies: service-role access only.

-- Remove public write access from server-side-only tables:
DROP POLICY IF EXISTS "public insert listings"              ON listings;
DROP POLICY IF EXISTS "public update listings"              ON listings;
DROP POLICY IF EXISTS "public insert listing_price_history" ON listing_price_history;
DROP POLICY IF EXISTS "public insert listing_sale_matches"  ON listing_sale_matches;
DROP POLICY IF EXISTS "public update listing_sale_matches"  ON listing_sale_matches;
DROP POLICY IF EXISTS "public insert estate_aliases"        ON estate_aliases;
DROP POLICY IF EXISTS "public insert withdrawal_sweep_log"  ON withdrawal_sweep_log;
-- Public SELECT policies remain in place on all tables pending Netlify password
-- protection on the CMA app.
