#!/usr/bin/env python3
"""
Lightstone TransfersReport import pipeline for Groundwork / Home Ground Real Estate.

Usage:
    python scripts/import_lightstone.py --file data/raw/simbithi_lightstone_export.xlsx \
                                         --estate "Simbithi Eco Estate"
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime

import pandas as pd
from supabase import create_client, Client


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
    "Size (m²)":               "size_m2",
    "Price per m²":            "price_per_m2",
    "Possible Land Only":       "possible_land_only",
    "Buyer Type":               "buyer_type",
    "Seller Type":              "seller_type",
    "Number of Owners":         "number_of_owners",
}

# Known sectional-scheme name deduplication
SCHEME_ALIASES = {
    "SS EDGE VIEWS": "SS EDGE VIEW",
}

# Max parcel size before we exclude as a non-dwelling land parcel
MAX_SIZE_M2 = 50_000


def normalise_scheme(val: str | None) -> str | None:
    if not val or (isinstance(val, float)):
        return None
    cleaned = re.sub(r"\s+", " ", str(val).upper().strip())
    return SCHEME_ALIASES.get(cleaned, cleaned)


def parse_land_only(val) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().upper() in ("Y", "YES", "TRUE", "1")
    return bool(val) if pd.notna(val) else False


BUYER_SELLER_MAP = {
    "natural person":  "natural_person",
    "individual":      "natural_person",
    "private person":  "natural_person",
    "legal entity":    "legal_entity",
    "company":         "legal_entity",
    "trust":           "legal_entity",
    "close corporation": "legal_entity",
    "cc":              "legal_entity",
}


def normalise_party_type(val) -> str | None:
    if not val or (isinstance(val, float) and pd.isna(val)):
        return None
    key = str(val).strip().lower()
    return BUYER_SELLER_MAP.get(key, "natural_person" if "person" in key or "individual" in key else "legal_entity")


def derive_property_type(title_deed_no: str | None) -> str | None:
    if not title_deed_no:
        return None
    prefix = str(title_deed_no).strip().upper()
    if prefix.startswith("ST"):
        return "sectional_title"
    if prefix.startswith("T"):
        return "freehold"
    return None


def to_int_or_none(val) -> int | None:
    try:
        v = int(val)
        return v
    except (TypeError, ValueError):
        return None


def to_date_or_none(val) -> str | None:
    if pd.isna(val) if not isinstance(val, str) else False:
        return None
    try:
        return pd.to_datetime(val).strftime("%Y-%m-%d")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Import a Lightstone TransfersReport xlsx into Supabase.")
    parser.add_argument("--file",   required=True, help="Path to the xlsx file")
    parser.add_argument("--estate", required=True, help="Estate name to tag records with")
    args = parser.parse_args()

    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SECRET_KEY")
    if not supabase_url or not supabase_key:
        sys.exit("Error: SUPABASE_URL and SUPABASE_SECRET_KEY environment variables must be set.")

    supabase: Client = create_client(supabase_url, supabase_key)

    print(f"\nReading {args.file} …")
    df = pd.read_excel(args.file, dtype=str)  # read everything as str first
    records_raw = len(df)
    print(f"  Rows read: {records_raw}")

    # Rename columns to schema names; keep only known columns
    df = df.rename(columns=COLUMN_MAP)
    known_cols = list(COLUMN_MAP.values())
    df = df[[c for c in known_cols if c in df.columns]]

    exclusions: dict[str, list[int]] = {
        "missing_title_deed_no":    [],
        "missing_registration_date": [],
        "oversized_parcel":         [],
    }

    rows: list[dict] = []
    for idx, row in df.iterrows():
        row_num = int(idx) + 2  # 1-based with header

        title_deed_no = str(row.get("title_deed_no", "") or "").strip()
        if not title_deed_no:
            exclusions["missing_title_deed_no"].append(row_num)
            continue

        registration_date = to_date_or_none(row.get("registration_date"))
        if not registration_date:
            exclusions["missing_registration_date"].append(row_num)
            continue

        size_m2 = to_int_or_none(row.get("size_m2"))
        if size_m2 is not None and size_m2 > MAX_SIZE_M2:
            exclusions["oversized_parcel"].append(row_num)
            continue

        sales_price_raw = to_int_or_none(row.get("sales_price"))
        possible_land_only = parse_land_only(row.get("possible_land_only"))
        is_market_sale = (
            sales_price_raw is not None
            and sales_price_raw > 1000
            and not possible_land_only
        )

        unit_val = str(row.get("unit", "") or "").strip() or None

        record = {
            "title_deed_no":      title_deed_no,
            "estate":             args.estate,
            "township":           str(row.get("township", "") or "").strip() or None,
            "erf":                to_int_or_none(row.get("erf")),
            "portion":            to_int_or_none(row.get("portion")) or 0,
            "sectional_scheme":   normalise_scheme(row.get("sectional_scheme")),
            "unit":               unit_val,
            "suburb":             str(row.get("suburb", "") or "").strip() or None,
            "street":             str(row.get("street", "") or "").strip() or None,
            "street_number":      str(row.get("street_number", "") or "").strip() or None,
            "sales_date":         to_date_or_none(row.get("sales_date")),
            "registration_date":  registration_date,
            "sales_price":        sales_price_raw,
            "size_m2":            size_m2,
            "price_per_m2":       to_int_or_none(row.get("price_per_m2")),
            "possible_land_only": possible_land_only,
            "buyer_type":         normalise_party_type(row.get("buyer_type")),
            "seller_type":        normalise_party_type(row.get("seller_type")),
            "number_of_owners":   to_int_or_none(row.get("number_of_owners")),
            "property_type":      derive_property_type(title_deed_no),
            "is_market_sale":     is_market_sale,
            "data_source":        "lightstone_export",
        }
        rows.append(record)

    records_excluded = records_raw - len(rows)
    records_imported = 0

    exclusion_summary = {
        reason: {"count": len(idxs), "row_numbers": idxs[:20]}  # cap sample at 20
        for reason, idxs in exclusions.items()
        if idxs
    }

    # Upsert in batches of 500
    BATCH = 500
    print(f"\nUpserting {len(rows)} records to Supabase …")
    for i in range(0, len(rows), BATCH):
        batch = rows[i : i + BATCH]
        result = (
            supabase.table("transactions")
            .upsert(batch, on_conflict="title_deed_no,unit")
            .execute()
        )
        records_imported += len(batch)
        print(f"  Batch {i // BATCH + 1}: {len(batch)} rows upserted")

    # Write import log
    log_entry = {
        "filename":          os.path.basename(args.file),
        "estate":            args.estate,
        "records_raw":       records_raw,
        "records_imported":  records_imported,
        "records_excluded":  records_excluded,
        "exclusion_summary": exclusion_summary,
    }
    supabase.table("import_log").insert(log_entry).execute()

    # Summary
    print("\n" + "=" * 60)
    print(f"Import complete — {args.estate}")
    print(f"  Total rows in file : {records_raw}")
    print(f"  Imported           : {records_imported}")
    print(f"  Excluded           : {records_excluded}")
    if exclusion_summary:
        for reason, info in exclusion_summary.items():
            print(f"    • {reason}: {info['count']}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
