-- import_log was only written on fully successful runs, leaving no trace of partial
-- or failed imports. Adds run status so the script can always write a log row.

ALTER TABLE import_log
  ADD COLUMN IF NOT EXISTS status        text CHECK (status IN ('success','partial','failed')) DEFAULT 'success',
  ADD COLUMN IF NOT EXISTS error_message text;
