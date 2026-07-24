#!/usr/bin/env python3
"""
Lightstone TransfersReport import pipeline for Groundwork / Home Ground Real Estate.

Requires migrations 011 and 012 to be applied before running.

Usage:
    python scripts/import_lightstone.py --file data/raw/simbithi_lightstone_export.xlsx \
                                         --estate "Simbithi Eco Estate"

    # To add an estate not yet in the canonical list:
    python scripts/import_lightstone.py --file data/raw/new_estate.xlsx \
                                         --estate "New Estate Name" --new-estate
"""

import argparse
import difflib
import json
import os
import re
import sys
from datetime import datetime

import pandas as pd
from supabase import create_client, Client


# ---------------------------------------------------------------------------
# Canonical estate names — must match CLAUDE.md section 4 exactly
# ---------------------------------------------------------------------------

CANONICAL_ESTATES = (
    "Simbithi Eco Estate",
    "Dunkirk Estate",
    "Ballito",
    "Black Rock",
    "Brettenwood Coastal Estate",
    "Compensation Beach",
    "Salt Rock",
    "Shakas Rock",
    "Thompsons Bay",
    "Umhlali Beach",
    "Willard Beach",
    "Elaleni Coastal Estate",
    "Zululami Luxury Coastal Estate",
    "Seaton",
    "Sheffield Beach",
)

# ---------------------------------------------------------------------------
# Column-name mapping  (Lightstone export header → schema field)
# ---------------------------------------------------------------------------

COLUMN_MAP = {
    "Title Deed No":            "title_deed_no",
    "Township":                 "township",
    "Erf":                      "erf",
    "Portion":                  "portion",
    "Sectional Scheme":         "sectional_scheme",
    "Unit":                     "unit",
    "Suburb":                   "suburb",
    "Street":                   "street",
    "Street Number":            "street_number",
    "Sales Date":               "sales_date",
    "Registration Date":        "registration_date",
    "Sales Price":              "sales_price",
    "Possible Land Only":       "possible_land_only",
    "Buyer":                    "buyer_type",
    "Seller":                   "seller_type",
    "Size":                     "size_m2",
    "R/m²":                    "price_per_m2",
    "Number of Owners":         "number_of_owners",
    # Per-row authoritative estate from Lightstone — used instead of --estate arg
    # when the value matches a canonical estate name.
    "Estate":                   "source_estate",
}

# Headers that must be present in the source file (subset of COLUMN_MAP keys)
REQUIRED_SOURCE_HEADERS = {
    "Title Deed No",
    "Registration Date",
    "Sales Price",
    "Size",
    "Erf",
    "Unit",
    "Sectional Scheme",
    "Portion",
    "Estate",
}

# Known sectional-scheme name deduplication
SCHEME_ALIASES = {
    "SS EDGE VIEWS": "SS EDGE VIEW",
}

# Cleaning rule: parcels larger than this are excluded as non-dwelling land (see CLAUDE.md)
MAX_SIZE_M2 = 50_000

# Cleaning rule: sales at or below this threshold are retained but marked is_market_sale=false
MARKET_SALE_MIN_PRICE = 1_000

_NULL_STRINGS = {"nan", "none", "null", "n/a", "na", ""}

_DATE_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d %b %Y",
)


def clean_str(val) -> str | None:
    """Strip whitespace and return None for blank/NaN-like cell values."""
    if val is None:
        return None
    s = str(val).strip()
    return None if s.lower() in _NULL_STRINGS else s


def normalise_scheme(val) -> str | None:
    s = clean_str(val)
    if not s:
        return None
    cleaned = re.sub(r"\s+", " ", s.upper())
    return SCHEME_ALIASES.get(cleaned, cleaned)


def parse_land_only(val) -> bool:
    s = clean_str(val)
    if s is None:
        return False
    return s.upper() in ("Y", "YES", "TRUE", "1")


BUYER_SELLER_MAP = {
    "natural person":    "natural_person",
    "individual":        "natural_person",
    "private person":    "natural_person",
    "legal entity":      "legal_entity",
    "company":           "legal_entity",
    "trust":             "legal_entity",
    "close corporation": "legal_entity",
    "cc":                "legal_entity",
}


def normalise_party_type(val, field: str, warnings: dict, unknown_vals: dict) -> str | None:
    s = clean_str(val)
    if not s:
        return None
    key = s.lower()
    result = BUYER_SELLER_MAP.get(key)
    if result is None:
        warnings[field] = warnings.get(field, 0) + 1
        examples = unknown_vals.setdefault(field, [])
        if s not in examples and len(examples) < 10:
            examples.append(s)
    return result


def derive_property_type(title_deed_no: str | None) -> str | None:
    if not title_deed_no:
        return None
    prefix = title_deed_no.upper()
    if prefix.startswith("ST"):
        return "sectional_title"
    if prefix.startswith("T"):
        return "freehold"
    return None


def to_int_or_none(val) -> int | None:
    s = clean_str(val)
    if not s:
        return None
    # Strip currency symbols and numeric separators (including non-breaking space \xa0)
    s = s.replace("R", "").replace(",", "").replace(" ", "").replace("\xa0", "")
    try:
        return int(float(s))
    except (TypeError, ValueError):
        return None


def to_date_or_none(val) -> str | None:
    s = clean_str(val)
    if not s:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    # Final fallback: pandas with dayfirst (South African convention)
    ts = pd.to_datetime(s, dayfirst=True, errors="coerce")
    return None if pd.isna(ts) else ts.strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Post-import regression check
# ---------------------------------------------------------------------------

def check_township_estate_date_gaps(supabase: Client, townships: set[str], import_max_date: str | None) -> None:
    """
    Warn if any estate sharing a township with this import has a max
    registration_date more than 180 days behind the import's own max date.

    This detects the misclassification pattern where rows belonging to a
    sub-estate (e.g. Elaleni) were instead tagged under a broader estate
    (e.g. Sheffield Beach) that shares the same township — causing the
    sub-estate's coverage to silently stop while the broader estate's
    coverage continued to grow.
    """
    if not townships or not import_max_date:
        return

    try:
        import_max_dt = datetime.strptime(import_max_date, "%Y-%m-%d").date()
    except ValueError:
        return

    # Fetch estate + registration_date for these townships, paginated
    estate_max: dict[str, str] = {}
    offset = 0
    page_size = 1000
    while True:
        result = (
            supabase.table("transactions")
            .select("estate, registration_date")
            .in_("township", list(townships))
            .range(offset, offset + page_size - 1)
            .execute()
        )
        for row in result.data:
            e, d = row.get("estate"), row.get("registration_date")
            if e and d and d > estate_max.get(e, ""):
                estate_max[e] = d
        if len(result.data) < page_size:
            break
        offset += page_size

    GAP_THRESHOLD_DAYS = 180
    gaps = []
    for estate, max_date_str in sorted(estate_max.items()):
        try:
            estate_max_dt = datetime.strptime(max_date_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue
        gap = (import_max_dt - estate_max_dt).days
        if gap > GAP_THRESHOLD_DAYS:
            gaps.append((estate, max_date_str, gap))

    if gaps:
        print("\nREGRESSION WARNING — township/estate date gap(s) detected:")
        print(f"  Import max registration_date : {import_max_date}")
        print("  Estates in the same township(s) with max date >180 days behind:")
        for estate, max_date, gap in gaps:
            print(f"    • {estate}: last seen {max_date} ({gap}d gap)")
        print("  This may indicate rows for those estates were misclassified as a")
        print("  different estate. Re-run with corrected estate assignment to fix.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Import a Lightstone TransfersReport xlsx into Supabase.")
    parser.add_argument("--file",       required=True, help="Path to the xlsx file")
    parser.add_argument("--estate",     required=True, help="Estate name to tag records with")
    parser.add_argument("--new-estate", action="store_true",
                        help="Bypass canonical estate validation for a new estate")
    args = parser.parse_args()

    # Estate validation
    if not args.new_estate and args.estate not in CANONICAL_ESTATES:
        closest = difflib.get_close_matches(args.estate, CANONICAL_ESTATES, n=3, cutoff=0.4)
        print(f"Error: '{args.estate}' is not a canonical estate name.")
        print("Canonical estates:")
        for name in CANONICAL_ESTATES:
            print(f"  • {name}")
        if closest:
            print(f"Did you mean: {', '.join(repr(c) for c in closest)}?")
        print("Use --new-estate to bypass this check for a genuinely new estate.")
        sys.exit(1)

    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SECRET_KEY")
    if not supabase_url or not supabase_key:
        sys.exit("Error: SUPABASE_URL and SUPABASE_SECRET_KEY environment variables must be set.")

    supabase: Client = create_client(supabase_url, supabase_key)

    print(f"\nReading {args.file} …")
    df = pd.read_excel(args.file, dtype=str)  # read everything as str first
    records_raw = len(df)
    print(f"  Rows read: {records_raw}")

    # Header validation — fail loudly before any processing
    found_headers = set(df.columns)
    missing = REQUIRED_SOURCE_HEADERS - found_headers
    if missing:
        print("Error: required source headers are missing from the file.")
        print(f"  Missing : {sorted(missing)}")
        print(f"  Found   : {sorted(found_headers)}")
        sys.exit(1)

    # Rename columns to schema names; keep only known columns
    df = df.rename(columns=COLUMN_MAP)
    known_cols = list(COLUMN_MAP.values())
    df = df[[c for c in known_cols if c in df.columns]]

    exclusions: dict[str, list[int]] = {
        "missing_title_deed_no":     [],
        "missing_registration_date": [],
        "oversized_parcel":          [],
        "uncovered_estate":          [],   # non-blank source_estate not in CANONICAL_ESTATES
    }
    # Separate counter so we know exactly how many rows per uncovered estate name
    uncovered_estate_counts: dict[str, int] = {}

    # Parse-failure warnings: counts of non-empty cells that produced None
    warnings: dict[str, int] = {}
    unknown_party_vals: dict[str, list[str]] = {}

    # Estate-source tracking: how many rows used per-row estate vs CLI fallback
    estate_from_source = 0
    estate_from_cli = 0
    unknown_source_estates: list[str] = []  # non-canonical source Estate values, capped at 10
    estate_distribution: dict[str, int] = {}

    # For the abort threshold check
    reg_date_nonempty = 0
    reg_date_failed   = 0
    price_nonempty    = 0
    price_failed      = 0

    rows: list[dict] = []
    for idx, row in df.iterrows():
        row_num = int(idx) + 2  # 1-based with header

        title_deed_no = clean_str(row.get("title_deed_no"))
        if not title_deed_no:
            exclusions["missing_title_deed_no"].append(row_num)
            continue

        raw_reg = clean_str(row.get("registration_date"))
        if raw_reg:
            reg_date_nonempty += 1
        registration_date = to_date_or_none(row.get("registration_date"))
        if raw_reg and not registration_date:
            reg_date_failed += 1
        if not registration_date:
            exclusions["missing_registration_date"].append(row_num)
            continue

        size_m2_raw = clean_str(row.get("size_m2"))
        size_m2 = to_int_or_none(row.get("size_m2"))
        if size_m2_raw and size_m2 is None:
            warnings["size_m2"] = warnings.get("size_m2", 0) + 1
        if size_m2 is not None and size_m2 > MAX_SIZE_M2:
            exclusions["oversized_parcel"].append(row_num)
            continue

        raw_price = clean_str(row.get("sales_price"))
        if raw_price:
            price_nonempty += 1
        sales_price_raw = to_int_or_none(row.get("sales_price"))
        if raw_price and sales_price_raw is None:
            price_failed += 1
            warnings["sales_price"] = warnings.get("sales_price", 0) + 1

        raw_ppm = clean_str(row.get("price_per_m2"))
        price_per_m2 = to_int_or_none(row.get("price_per_m2"))
        if raw_ppm and price_per_m2 is None:
            warnings["price_per_m2"] = warnings.get("price_per_m2", 0) + 1

        raw_sd = clean_str(row.get("sales_date"))
        sales_date = to_date_or_none(row.get("sales_date"))
        if raw_sd and sales_date is None:
            warnings["sales_date"] = warnings.get("sales_date", 0) + 1

        raw_noo = clean_str(row.get("number_of_owners"))
        number_of_owners = to_int_or_none(row.get("number_of_owners"))
        if raw_noo and number_of_owners is None:
            warnings["number_of_owners"] = warnings.get("number_of_owners", 0) + 1

        possible_land_only = parse_land_only(row.get("possible_land_only"))
        is_market_sale = (
            sales_price_raw is not None
            and sales_price_raw > MARKET_SALE_MIN_PRICE
            and not possible_land_only
        )

        # Determine estate from the per-row "Estate" source column.
        #
        # Case 1 — source_estate is blank/null: row is from the general geographic
        #   area of the export but not assigned to a specific sub-estate. Default to
        #   args.estate (what this export was pulled around).
        #
        # Case 2 — source_estate is a non-blank value NOT in CANONICAL_ESTATES: the
        #   row definitively belongs to a different, currently-uncovered estate. Do
        #   NOT reassign it to args.estate — exclude it instead so uncovered estates
        #   are surfaced explicitly rather than silently merged into the wrong bucket.
        #
        # Case 3 — source_estate is a canonical estate name: use it directly.
        source_estate = clean_str(row.get("source_estate"))
        if source_estate and source_estate not in CANONICAL_ESTATES:
            # Case 2: known-different, uncovered estate — exclude
            exclusions["uncovered_estate"].append(row_num)
            uncovered_estate_counts[source_estate] = uncovered_estate_counts.get(source_estate, 0) + 1
            continue
        elif source_estate:
            # Case 3: canonical match
            row_estate = source_estate
            estate_from_source += 1
        else:
            # Case 1: blank — default to CLI arg
            row_estate = args.estate
            estate_from_cli += 1
        estate_distribution[row_estate] = estate_distribution.get(row_estate, 0) + 1

        record = {
            "title_deed_no":      title_deed_no,
            "estate":             row_estate,
            "township":           clean_str(row.get("township")),
            "erf":                to_int_or_none(row.get("erf")),
            "portion":            to_int_or_none(row.get("portion")) or 0,
            "sectional_scheme":   normalise_scheme(row.get("sectional_scheme")),
            "unit":               clean_str(row.get("unit")),
            "suburb":             clean_str(row.get("suburb")),
            "street":             clean_str(row.get("street")),
            "street_number":      clean_str(row.get("street_number")),
            "sales_date":         sales_date,
            "registration_date":  registration_date,
            "sales_price":        sales_price_raw,
            "size_m2":            size_m2,
            "price_per_m2":       price_per_m2,
            "possible_land_only": possible_land_only,
            "buyer_type":         normalise_party_type(row.get("buyer_type"),  "buyer_type",  warnings, unknown_party_vals),
            "seller_type":        normalise_party_type(row.get("seller_type"), "seller_type", warnings, unknown_party_vals),
            "number_of_owners":   number_of_owners,
            "property_type":      derive_property_type(title_deed_no),
            "is_market_sale":     is_market_sale,
            "data_source":        "lightstone_export",
        }
        rows.append(record)

    # Abort if more than 20% of non-empty critical fields failed to parse
    if reg_date_nonempty > 0 and reg_date_failed / reg_date_nonempty > 0.20:
        sys.exit(
            f"Aborting: {reg_date_failed}/{reg_date_nonempty} non-empty registration_date "
            f"values failed to parse ({reg_date_failed/reg_date_nonempty:.0%}). "
            "File format may have changed."
        )
    if price_nonempty > 0 and price_failed / price_nonempty > 0.20:
        sys.exit(
            f"Aborting: {price_failed}/{price_nonempty} non-empty sales_price "
            f"values failed to parse ({price_failed/price_nonempty:.0%}). "
            "File format may have changed."
        )

    # In-memory dedupe on natural key before upsert
    natural_key = lambda r: (
        r["title_deed_no"],
        r["unit"] or "",
        r["erf"] if r["erf"] is not None else -1,
        r["portion"],
    )
    seen: dict[tuple, int] = {}  # key → index in rows
    for i, r in enumerate(rows):
        seen[natural_key(r)] = i  # last occurrence wins
    deduped_indices = set(seen.values())
    dropped = [i for i in range(len(rows)) if i not in deduped_indices]
    if dropped:
        print(f"\nWARNING: {len(dropped)} in-file duplicate(s) dropped before upsert "
              f"(kept last occurrence). Source row indices (0-based): {dropped}")
    rows = [rows[i] for i in sorted(deduped_indices)]

    records_excluded = records_raw - len(rows)

    exclusion_summary: dict = {}
    for reason, idxs in exclusions.items():
        if idxs:
            entry: dict = {"count": len(idxs), "row_numbers": idxs[:20]}
            if len(idxs) > 20:
                entry["truncated"] = True
            if reason == "uncovered_estate":
                entry["by_estate"] = uncovered_estate_counts
            exclusion_summary[reason] = entry
    if warnings:
        exclusion_summary["warnings"] = dict(warnings)
        if unknown_party_vals:
            exclusion_summary["unknown_party_values"] = unknown_party_vals
    if estate_from_source > 0 or unknown_source_estates:
        exclusion_summary["estate_source"] = {
            "per_row_from_source": estate_from_source,
            "cli_fallback":        estate_from_cli,
            "unknown_source_values": unknown_source_estates or None,
        }

    # Upsert in batches of 500 with error capture
    BATCH = 500
    records_imported = 0
    batches_completed = 0
    error_message: str | None = None

    print(f"\nUpserting {len(rows)} records to Supabase …")
    try:
        for i in range(0, len(rows), BATCH):
            batch = rows[i : i + BATCH]
            result = (
                supabase.table("transactions")
                .upsert(batch, on_conflict="title_deed_no,unit_key,erf_key,portion")
                .execute()
            )
            records_imported += len(batch)
            batches_completed += 1
            print(f"  Batch {batches_completed}: {len(batch)} rows upserted")
    except Exception as exc:
        error_message = str(exc)
        print(f"\nERROR during batch {batches_completed + 1}: {error_message}")
    finally:
        total_batches = -(-len(rows) // BATCH) if rows else 0  # ceiling div
        if error_message is None:
            status = "success"
        elif batches_completed == 0:
            status = "failed"
        else:
            status = "partial"

        log_entry = {
            "filename":          os.path.basename(args.file),
            "estate":            args.estate,
            "records_raw":       records_raw,
            "records_imported":  records_imported,
            "records_excluded":  records_excluded,
            "exclusion_summary": exclusion_summary,
            "status":            status,
            "error_message":     error_message,
        }
        try:
            supabase.table("import_log").insert(log_entry).execute()
        except Exception as log_exc:
            print(f"WARNING: could not write import_log row: {log_exc}")

    # Regression check: warn on township/estate date gaps
    if status in ("success", "partial") and rows:
        import_max_date = max((r["registration_date"] for r in rows if r.get("registration_date")), default=None)
        townships_in_import = {r["township"] for r in rows if r.get("township")}
        check_township_estate_date_gaps(supabase, townships_in_import, import_max_date)

    # Summary
    print("\n" + "=" * 60)
    print(f"Import complete — {args.estate}")
    print(f"  Total rows in file : {records_raw}")
    print(f"  Imported           : {records_imported}")
    print(f"  Excluded           : {records_excluded}")
    if len(estate_distribution) > 1 or (estate_distribution and list(estate_distribution)[0] != args.estate):
        print(f"  Estate distribution:")
        for e, count in sorted(estate_distribution.items()):
            source_label = " (from source)" if e != args.estate else " (CLI fallback)"
            print(f"    • {e}: {count}{source_label}")
    if unknown_source_estates:
        print(f"  Unknown source estates (mapped to '{args.estate}'): {unknown_source_estates}")
    if exclusion_summary:
        for reason, info in exclusion_summary.items():
            if reason == "warnings":
                for field, count in info.items():
                    print(f"    • parse_warning/{field}: {count}")
            elif reason in ("unknown_party_values", "estate_source"):
                pass  # printed above
            elif reason == "uncovered_estate":
                print(f"    • {reason}: {info['count']} rows excluded (uncovered estates):")
                for ename, ecount in sorted(info.get("by_estate", {}).items()):
                    print(f"        – {ename!r}: {ecount}")
            else:
                print(f"    • {reason}: {info['count']}")
    print(f"  Status             : {status}")
    if error_message:
        print(f"  Error              : {error_message}")
    print("=" * 60 + "\n")

    if status != "success":
        sys.exit(1)


if __name__ == "__main__":
    main()
