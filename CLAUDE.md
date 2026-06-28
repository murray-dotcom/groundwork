# Groundwork — CLAUDE.md

## 1. Project Overview

**Groundwork** is the property intelligence database for **Home Ground Real Estate**. It ingests Lightstone TransfersReport exports, cleans and normalises the data, and stores it in Supabase Postgres for property-market analysis and CMA (Comparative Market Analysis) tooling.

- **Supabase project URL:** `https://zumdsmmhsttnfruyvngq.supabase.co`
- **Anon key:** `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inp1bWRzbW1oc3R0bmZydXl2bmdxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODIzMjEwNzMsImV4cCI6MjA5Nzg5NzA3M30.Y_a6MAnOsUbsHRqzsoqw0w0Uo1lF5O3VLO7kpNJRpPM`

---

## 2. Database Schema

### `transactions`
Core table. One row per registered property transfer, sourced from Lightstone exports.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid | PK, auto-generated |
| `title_deed_no` | text | Raw deed number (e.g. `ST16279/2026`, `T1234/2020`) |
| `estate` | text | Estate/suburb tag set at import time — see canonical list below |
| `township` | text | |
| `erf` | integer | |
| `portion` | integer | Defaults to 0 |
| `sectional_scheme` | text | Normalised: uppercase, trimmed, aliases resolved |
| `unit` | text | Sectional-title unit number |
| `suburb` | text | |
| `street` | text | |
| `street_number` | text | |
| `sales_date` | date | |
| `registration_date` | date | Not null — primary temporal key |
| `sales_price` | bigint | |
| `size_m2` | integer | |
| `price_per_m2` | integer | |
| `possible_land_only` | boolean | |
| `buyer_type` | text | `natural_person` or `legal_entity` |
| `seller_type` | text | `natural_person` or `legal_entity` |
| `number_of_owners` | integer | |
| `property_type` | text | `sectional_title` (ST prefix) or `freehold` (T prefix) |
| `is_market_sale` | boolean | `sales_price > 1000 AND possible_land_only = false` |
| `data_source` | text | Defaults to `lightstone_export` |
| `imported_at` | timestamptz | |

Unique index: `(title_deed_no, COALESCE(unit, ''))` — used as the natural key for upserts.

---

### `property_attributes`
Broker-entered enrichment data, added manually when running CMAs.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid | PK |
| `title_deed_no` | text | FK reference to transactions |
| `estate` | text | |
| `built_area_m2` | integer | |
| `sea_view` | boolean | |
| `view_rating` | integer | 1–5 |
| `property_detail_type` | text | `house`, `townhouse`, `apartment`, `vacant_land`, `penthouse`, `duplex`, `simplex` |
| `condition_rating` | integer | 1–5 |
| `bedrooms` | integer | Added in 003 |
| `bathrooms` | integer | Added in 003 |
| `has_pool` | boolean | Added in 003 |
| `has_staff_accommodation` | boolean | Added in 003 |
| `has_stairs` | boolean | Added in 003 |
| `notes` | text | |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |

Unique on `(title_deed_no, estate)`. RLS enabled — public read/insert/update.

---

### `import_log`
Audit trail for every import run.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid | PK |
| `filename` | text | Source xlsx filename |
| `estate` | text | |
| `records_raw` | integer | |
| `records_imported` | integer | |
| `records_excluded` | integer | |
| `exclusion_summary` | jsonb | Breakdown by exclusion reason |
| `imported_at` | timestamptz | |

---

### `listings`
Active and historical property listings (agent-entered or scraped).

| Column | Type | Notes |
|---|---|---|
| `id` | uuid | PK |
| (see 004_listings.sql for full column list) | | Added in migration 004 |

---

### `listing_price_history`
Price change log for listings over time.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid | PK |
| (see 004_listings.sql for full column list) | | Added in migration 004 |

---

## 3. Data Conventions

### Numeric columns come back as strings from Supabase
`size_m2`, `sales_price`, and `price_per_m2` are returned as strings by the Supabase JS client. **Always cast with `Number()` before comparisons or arithmetic:**
```js
const pricePerM2 = Number(row.price_per_m2)
```

### ON CONFLICT DO NOTHING placement
`ON CONFLICT DO NOTHING` must appear **exactly once**, at the very end of the full INSERT statement — after the last `(...)` values row, never mid-statement:
```sql
INSERT INTO transactions (...) VALUES
(...),
(...),
(...)           -- last row, NO trailing comma
ON CONFLICT DO NOTHING;
```

### Seed file size limit
The Supabase SQL editor cannot handle large INSERT statements. **Split seed files at ~250 rows.** Name them `[estate]_insert_1.sql` and `[estate]_insert_2.sql`. Run `_1` first, then `_2`.

### Never use the Supabase CSV importer
The CSV importer silently drops `integer` columns. **Always use SQL INSERT files** with explicit type casts:
```sql
83::integer        -- size_m2
1450000::bigint    -- sales_price
17469::integer     -- price_per_m2
'2026-06-10'::date -- dates
TRUE               -- booleans
```

---

## 4. Canonical Estate Names

These are the exact strings stored in the `estate` column. Use them verbatim — casing and spacing must match exactly.

| Estate name |
|---|
| `Simbithi Eco Estate` |
| `Dunkirk Estate` |
| `Ballito` |
| `Black Rock` |
| `Brettenwood Coastal Estate` |
| `Compensation Beach` |
| `Salt Rock` |
| `Shakas Rock` |
| `Thompsons Bay` |
| `Umhlali Beach` |
| `Willard Beach` |
| `Elaleni Coastal Estate` |
| `Zululami Luxury Coastal Estate` |

---

## 5. Migration History

| File | What it adds |
|---|---|
| `001_initial_schema.sql` | `transactions` table + indexes + `import_log` table |
| `002_property_attributes.sql` | `property_attributes` enrichment table with RLS |
| `003_enrichment_specs.sql` | Adds `bedrooms`, `bathrooms`, `has_pool`, `has_staff_accommodation`, `has_stairs` columns to `property_attributes` |
| `004_listings.sql` | `listings` and `listing_price_history` tables |

Apply migrations in order via the Supabase SQL editor.

---

## 6. Workflow

- **Cloud only** — there is no local dev environment. All work runs in remote Claude Code sessions.
- **GitHub org:** `murray-dotcom`
- **Production branch:** `dev` (groundwork data repo)
- **All changes flow:** Claude Code → commit → push to `dev` → reviewed by Murray
- **No force-pushes** to `dev`.
- **Secrets** (service role key) are never committed. The anon key above is safe to commit.
