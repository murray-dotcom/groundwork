-- Applied directly in Supabase via Cowork. Records each run of the listing-withdrawal sweep job.
CREATE TABLE IF NOT EXISTS withdrawal_sweep_log (
  id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  run_at          timestamptz NOT NULL DEFAULT now(),
  withdrawn_count integer     NOT NULL,
  source_ids      jsonb
);

ALTER TABLE withdrawal_sweep_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "public read withdrawal_sweep_log"
  ON withdrawal_sweep_log FOR SELECT USING (true);
CREATE POLICY "public insert withdrawal_sweep_log"
  ON withdrawal_sweep_log FOR INSERT WITH CHECK (true);
