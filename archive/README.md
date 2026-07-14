# Archive — historical bootstrap data
These CSVs and seed SQL files were used for the initial one-time load of the
transactions table (via the Supabase SQL editor, ON CONFLICT DO NOTHING).
They are point-in-time snapshots and are now STALE. The live Supabase database
is the source of truth; all new data flows through scripts/import_lightstone.py.
Do not run these files. Do not treat them as current data.
