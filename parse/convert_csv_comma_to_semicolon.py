#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2025-2026 Louis TRIOULEYRE-ROBERJOT
# This file is part of TollData - Open French Highway Toll Database

import csv
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

INPUT_CSV = BASE_DIR / "peages_all.csv"
OUTPUT_CSV = BASE_DIR / "peages_all_semicolon.csv"

INPUT_DELIMITER = ","
OUTPUT_DELIMITER = ";"
CSV_QUOTECHAR = '"'
CSV_ENCODING = "utf-8"


def convert_csv_delimiter() -> int:
    if not INPUT_CSV.exists():
        print(f"[ERR] Fichier introuvable: {INPUT_CSV}", file=sys.stderr)
        return 1

    with (
        open(INPUT_CSV, "r", encoding=CSV_ENCODING, newline="") as fin,
        open(OUTPUT_CSV, "w", encoding=CSV_ENCODING, newline="") as fout,
    ):
        reader = csv.reader(
            fin,
            delimiter=INPUT_DELIMITER,
            quotechar=CSV_QUOTECHAR,
            doublequote=True,
        )
        writer = csv.writer(
            fout,
            delimiter=OUTPUT_DELIMITER,
            quotechar=CSV_QUOTECHAR,
            quoting=csv.QUOTE_MINIMAL,
            lineterminator="\n",
        )

        row_count = 0
        for row in reader:
            writer.writerow(row)
            row_count += 1

    print(f"OK -> {OUTPUT_CSV} ({row_count} lignes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(convert_csv_delimiter())
