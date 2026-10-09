"""Normalize a manually transcribed private TSV. No network access or public export.

Run: python3 scripts/normalize_catalog.py private/christmas-batch-001.tsv
The input is a curated transcription, NOT a parser for arbitrary scraper output.
"""
import csv
import json
import re
import sys
from decimal import Decimal
from pathlib import Path


def normalize(path):
    records = []
    seen = set()
    with Path(path).open(encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            number = int(row["row"])
            if number <= 0 or number in seen:
                raise ValueError("Invalid or duplicate source row")
            seen.add(number)
            match = re.fullmatch(r"\$([\d,]+(?:\.\d+)?)(?:-([\d,]+(?:\.\d+)?))?", row["price_display"])
            if not match:
                raise ValueError(f"Invalid price at row {number}")
            low = Decimal(match[1].replace(",", ""))
            high = Decimal((match[2] or match[1]).replace(",", ""))
            moq = int(row["moq"])
            if not 0 < low <= high or moq < 1 or row["moq_unit"] not in {"piece", "pieces", "set"}:
                raise ValueError(f"Invalid commercial values at row {number}")
            records.append({
                "source_row_id": f"1791343056-{number}",
                "description_summary": row["description_summary"],
                "supplier_as_listed_private": row["supplier_as_listed"],
                "advertised_price": {"display": row["price_display"], "min": str(low), "max": str(high),
                    "currency_symbol": "$", "currency_code": None, "unit_basis": None,
                    "exact_variant_confirmed": False},
                "advertised_moq": {"quantity": moq, "unit": row["moq_unit"]},
                "verification_status": "unverified_user_supplied_listing",
                "product_url": None,
                "scraped_at": None,
            })
    return {"schema_version": 1, "source": "User-pasted scraper text; manually transcribed summaries",
            "search_query": "christmas tree with lights 7.5 ft", "records": records}


if __name__ == "__main__":
    path = Path(sys.argv[1]).resolve()
    private = Path(__file__).resolve().parents[1] / "private"
    if not path.is_relative_to(private):
        raise SystemExit("Input must be under the ignored private directory")
    result = normalize(path)
    output = path.with_suffix(".json")
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output.chmod(0o600)
    print(f"Normalized {len(result['records'])} records into private storage")
