# Groundwork — Property Intelligence Database

Backend data infrastructure for **Home Ground Real Estate**. Ingests Lightstone TransfersReport exports, cleans and normalises the data, and loads it into a Supabase Postgres database for property-market analysis.

---

## Repo structure

```
groundwork/
├── archive/
│   ├── processed/                   # Historical cleaned CSVs (stale — do not use)
│   └── seeds/                       # Historical SQL seed files (stale — do not run)
├── data/
│   └── raw/                         # Source xlsx files (not committed to version control)
├── scripts/
│   ├── import_lightstone.py         # Main ETL script
│   └── requirements.txt             # Python dependencies
└── supabase/
    └── migrations/                  # 001 through 009 — apply in order via Supabase SQL editor
```

See [CLAUDE.md](CLAUDE.md) for the full schema reference and migration history.

---

## Setup

### 1. Create the database schema

Apply the migration to your Supabase project via the SQL editor or CLI:

```bash
# Using Supabase CLI
supabase db push

# Or paste supabase/migrations/001_initial_schema.sql into the Supabase SQL editor
```

### 2. Install Python dependencies

```bash
pip install -r scripts/requirements.txt
```

### 3. Set environment variables

```bash
export SUPABASE_URL="https://<your-project-ref>.supabase.co"
export SUPABASE_SECRET_KEY="<your-service-role-key>"
```

---

## Running the import

```bash
python scripts/import_lightstone.py \
    --file  data/raw/simbithi_lightstone_export.xlsx \
    --estate "Simbithi Eco Estate"

python scripts/import_lightstone.py \
    --file  data/raw/dunkirk_lightstone_export.xlsx \
    --estate "Dunkirk Estate"
```

The script prints a summary on completion:

```
============================================================
Import complete — Simbithi Eco Estate
  Total rows in file : 500
  Imported           : 415
  Excluded           : 85
    • oversized_parcel: 85
============================================================
```

Each run also inserts a row into the `import_log` table with the full exclusion breakdown.

Re-running is safe — records are **upserted** using `(title_deed_no, unit, erf, portion)` as the composite natural key, so duplicates are skipped rather than inserted twice. See [CLAUDE.md](CLAUDE.md) section 2 for the authoritative schema reference.

---

## Schema overview

See [CLAUDE.md](CLAUDE.md) section 2 for full schema documentation (`transactions`, `import_log`, `property_attributes`, `listings`, and all supporting tables).

---

## Cleaning rules applied at import

| Rule | Action |
|---|---|
| `title_deed_no` missing | Exclude |
| `registration_date` missing | Exclude |
| `size_m2 > 50 000` | Exclude (land parcels, not dwellings) |
| `sales_price ≤ 1000` or `possible_land_only = true` | Retain, but `is_market_sale = false` |
| Title deed prefix `ST…` | `property_type = 'sectional_title'` |
| Title deed prefix `T…` | `property_type = 'freehold'` |
| Sectional scheme name | Uppercased, whitespace normalised, known aliases merged (`SS EDGE VIEWS` → `SS EDGE VIEW`) |

---

## Data sources

- **Lightstone TransfersReport** — residential property transfer records exported from the Lightstone property intelligence platform, covering registered sales transactions within each estate.
- Seed data: Simbithi Eco Estate (500 records) and Dunkirk Estate (500 records).
