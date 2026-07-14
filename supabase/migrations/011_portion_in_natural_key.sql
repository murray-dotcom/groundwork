-- The natural key (title_deed_no, unit_key, erf_key) misses portion. Real Lightstone
-- data contains one deed transferring multiple portions of the same erf (e.g.
-- T74086/2025: portions 316 and 687 of erf 1521), which collided under the old key —
-- ON CONFLICT DO NOTHING silently dropped rows during seeding, and the import script's
-- upsert would either crash ("cannot affect row a second time") or silently overwrite.
-- Verified: zero NULL portions exist in the live table, so NOT NULL is safe.

UPDATE transactions SET portion = 0 WHERE portion IS NULL;  -- belt and braces
ALTER TABLE transactions ALTER COLUMN portion SET DEFAULT 0;
ALTER TABLE transactions ALTER COLUMN portion SET NOT NULL;

DROP INDEX IF EXISTS transactions_natural_key;
CREATE UNIQUE INDEX transactions_natural_key
  ON transactions (title_deed_no, unit_key, erf_key, portion);
