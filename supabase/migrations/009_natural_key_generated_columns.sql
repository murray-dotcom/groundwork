-- Replace the expression-based unique index with stored generated columns so that
-- PostgREST's on_conflict parameter (which only accepts column names) can target
-- the natural key directly, enabling the import script's .upsert() to work correctly.

-- Drop the old expression index
DROP INDEX IF EXISTS transactions_natural_key;

-- Add stable, stored representations of the COALESCE expressions
ALTER TABLE transactions
  ADD COLUMN unit_key text    GENERATED ALWAYS AS (COALESCE(unit, ''))  STORED,
  ADD COLUMN erf_key  integer GENERATED ALWAYS AS (COALESCE(erf,  -1)) STORED;

-- Recreate the unique constraint on the generated columns
CREATE UNIQUE INDEX transactions_natural_key
  ON transactions (title_deed_no, unit_key, erf_key);
