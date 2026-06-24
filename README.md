# Groundwork — Property Intelligence Database

Backend data infrastructure for **Home Ground Real Estate**. Ingests Lightstone TransfersReport exports, cleans and normalises the data, and loads it into a Supabase Postgres database for property-market analysis.

---

## Repo structure

```
groundwork/
├── data/
│   └── raw/                         # Source xlsx files (not committed to version control)
│       ├── simbithi_lightstone_export.xlsx
│       └── dunkirk_lightstone_export.xlsx
├── scripts/
│   ├── import_lightstone.py         # Main ETL script
│   └── requirements.txt             # Python dependencies
└── supabase/
    └── migrations/
        └── 001_initial_schema.sql   # Transactions + import_log tables
```

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

Re-running is safe — records are **upserted** using `title_deed_no + unit` as the composite natural key, so duplicates are overwritten rather than inserted twice.

---

## Schema overview

### `transactions`

| Column | Type | Notes |
|---|---|---|
| `id` | uuid | Primary key |
| `title_deed_no` | text | Raw deed number from Lightstone |
| `estate` | text | Estate tag set at import time |
| `township` | text | |
| `erf` | integer | |
| `portion` | integer | Defaults to 0 |
| `sectional_scheme` | text | Normalised: uppercase, trimmed, aliases resolved |
| `unit` | text | Sectional-title unit number |
| `suburb` | text | |
| `street` | text | |
| `street_number` | text | |
| `sales_date` | date | |
| `registration_date` | date | Not null; used as primary temporal key |
| `sales_price` | bigint | Raw value from Lightstone |
| `size_m2` | integer | |
| `price_per_m2` | integer | |
| `possible_land_only` | boolean | Y/N flag from source, converted to boolean |
| `buyer_type` | text | `natural_person` or `legal_entity` |
| `seller_type` | text | `natural_person` or `legal_entity` |
| `number_of_owners` | integer | |
| `property_type` | text | `sectional_title` (ST prefix) or `freehold` (T prefix) |
| `is_market_sale` | boolean | `sales_price > 1000 AND possible_land_only = false` |
| `data_source` | text | Defaults to `lightstone_export` |
| `imported_at` | timestamptz | |

### `import_log`

Audit trail of every import run — file name, estate, raw/imported/excluded counts, and a JSONB exclusion breakdown.

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
