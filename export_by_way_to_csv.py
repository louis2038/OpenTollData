#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2025-2026 Louis TRIOULEYRE-ROBERJOT
# This file is part of TollData - Open French Highway Toll Database
"""
Export a simplified CSV from the enriched price_format JSON.

Input JSON must contain a top-level "by_way" block like:
"by_way": {
  "48201983": {
    "length": "0.024",
    "average_price": {
      "class_1": "6.8",
      ...
    },
    "relation": [ ... ]
  },
  ...
}

The CSV columns are:
way_id,length_km,class_1_mean_per_km,class_2_mean_per_km,class_3_mean_per_km,class_4_mean_per_km,class_5_mean_per_km

By default, values are written with up to 10 decimal places, no scientific notation.

Usage:
  python export_by_way_to_csv.py --json price_with_by_way.json --out by_way_summary.csv
  # Optional: --sig 2  (minimum significant digits when formatting numbers as strings in CSV)
"""

import argparse
import csv
import json
from decimal import Decimal, ROUND_HALF_UP, getcontext

def to_float(s):
    if s is None:
        return 0.0
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s).strip().replace(',', '.')
    try:
        return float(s)
    except Exception:
        return 0.0

def format_number(x: float, sig: int = 0) -> str:
    """
    Format a float without scientific notation.
    - If sig >= 2, ensure at least 'sig' significant digits.
    - Otherwise, clamp to 10 decimal places.
    """
    if sig and sig >= 2:
        # Use Decimal for significant-figure formatting
        if x == 0.0:
            return "0"
        # Determine exponent (order of magnitude)
        import math
        exp = math.floor(math.log10(abs(x)))
        # scale number to have 'sig' digits before rounding
        scale = sig - exp - 1
        getcontext().prec = sig + 5  # guard digits
        q = Decimal(str(x))
        if scale >= 0:
            quant = Decimal(1).scaleb(-scale)  # 10^-scale
        else:
            quant = Decimal(1).scaleb(-scale)  # still works for negative scale
        # Quantize to the required scale, then format
        y = q.quantize(quant, rounding=ROUND_HALF_UP)
        s = format(y, 'f')  # no scientific
        # strip trailing zeros and dot
        if '.' in s:
            s = s.rstrip('0').rstrip('.')
        return s if s else "0"
    else:
        # default: 10 decimals, no scientific
        s = f"{x:.10f}"
        # strip trailing zeros and dot
        if '.' in s:
            s = s.rstrip('0').rstrip('.')
        return s if s else "0"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", required=True, help="Input JSON with top-level by_way")
    ap.add_argument("--out", required=True, help="Output CSV path")
    ap.add_argument("--sig", type=int, default=0, help="Minimum significant digits (>=2 to enable)")
    args = ap.parse_args()

    with open(args.json, "r", encoding="utf-8") as f:
        data = json.load(f)

    by_way = data.get("by_way", {})
    class_cols = [f"class_{i}_mean_per_km" for i in range(1, 6)]

    rows = []
    for way_id_str, info in by_way.items():
        length_km = to_float(info.get("length"))
        avg = info.get("average_price", {}) or {}
        # compute mean per km: average_price / length_km (guard zero)
        vals = []
        for i in range(1, 6):
            v = to_float(avg.get(f"class_{i}"))
            if length_km > 0:
                vals.append(v / length_km)
            else:
                vals.append(0.0)

        row = {
            "way_id": way_id_str,
            "length_km": format_number(length_km, sig=args.sig),
        }
        for i, col in enumerate(class_cols):
            row[col] = format_number(vals[i], sig=args.sig)
        rows.append(row)

    # Write CSV
    fieldnames = ["way_id", "length_km"] + class_cols
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    print(f"Wrote {len(rows)} rows to {args.out}")

if __name__ == "__main__":
    main()
