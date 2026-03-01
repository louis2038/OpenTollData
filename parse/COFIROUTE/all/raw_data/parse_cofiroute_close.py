#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2025-2026 Louis TRIOULEYRE-ROBERJOT
# This file is part of TollData - Open French Highway Toll Database

import csv
import re
import sys
import unicodedata
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = BASE_DIR / "cofiroute_data.txt"
OUTPUT_PRICE_CSV = BASE_DIR / "COFIROUTE_data_price_close_2026.csv"
OUTPUT_STATIONS_CSV = BASE_DIR / "COFIROUTE_toll_info_2026.csv"

CSV_DELIMITER = ";"
DISTANCE_DEFAULT = ""

# Noms de gares a exclure (normalisation appliquee automatiquement).
EXCLUDED_STATIONS = {
    # "EXEMPLE GARE A EXCLURE",
}

# Fichier optionnel contenant des gares a exclure (1 nom par ligne).
# Mettre a None pour desactiver.
EXCLUDED_STATIONS_FILE = None


LINE_RE = re.compile(
    r"""^\s*
    (?P<route_from>[A-Z]\d+)\s+
    (?P<exit_from>[0-9]+(?:\.[0-9]+)?|-)\s+
    (?P<name_from>.+?)\s+
    (?P<route_to>[A-Z]\d+)\s+
    (?P<exit_to>[0-9]+(?:\.[0-9]+)?|-)\s+
    (?P<name_to>.+?)\s+
    (?P<price1>\d+,\d{2})\s*€\s+
    (?P<price2>\d+,\d{2})\s*€\s+
    (?P<price3>\d+,\d{2})\s*€\s+
    (?P<price4>\d+,\d{2})\s*€\s+
    (?P<price5>\d+,\d{2})\s*€\s*
    $""",
    re.VERBOSE,
)


def normalize_name(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )
    s = re.sub(r"[^A-Za-z0-9]", " ", s)
    s = re.sub(r"\s+", " ", s)
    s = s.strip()
    return s.upper()


def fr_to_float_str(x: str) -> str:
    return x.replace(",", ".")


def load_excluded_stations() -> set[str]:
    excluded = {normalize_name(name) for name in EXCLUDED_STATIONS if name.strip()}

    if EXCLUDED_STATIONS_FILE:
        path = Path(EXCLUDED_STATIONS_FILE)
        if not path.is_absolute():
            path = BASE_DIR / path
        if not path.exists():
            print(f"[WARN] Fichier d'exclusion introuvable: {path}", file=sys.stderr)
        else:
            for raw in path.read_text(encoding="utf-8").splitlines():
                name = raw.strip()
                if not name or name.startswith("#"):
                    continue
                excluded.add(normalize_name(name))

    return excluded


def parse_lines(lines: list[str], excluded_stations: set[str]):
    rows = []
    stations = set()
    excluded_count = 0
    unparsed_count = 0

    for i, raw in enumerate(lines, 1):
        line = re.sub(r"\s+", " ", raw.strip())
        if not line:
            continue

        m = LINE_RE.match(line)
        if not m:
            unparsed_count += 1
            print(f"[WARN] Ligne {i} non reconnue: {line}", file=sys.stderr)
            continue

        d = m.groupdict()
        name_from = normalize_name(d["name_from"])
        name_to = normalize_name(d["name_to"])

        if name_from in excluded_stations or name_to in excluded_stations:
            excluded_count += 1
            continue

        rows.append(
            [
                name_from,
                name_to,
                DISTANCE_DEFAULT,
                fr_to_float_str(d["price1"]),
                fr_to_float_str(d["price2"]),
                fr_to_float_str(d["price3"]),
                fr_to_float_str(d["price4"]),
                fr_to_float_str(d["price5"]),
            ]
        )
        stations.add(name_from)
        stations.add(name_to)

    return rows, stations, excluded_count, unparsed_count


def write_price_csv(rows: list[list[str]]) -> None:
    with open(OUTPUT_PRICE_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=CSV_DELIMITER)
        w.writerow(
            [
                "name_from",
                "name_to",
                "distance",
                "price1",
                "price2",
                "price3",
                "price4",
                "price5",
            ]
        )
        w.writerows(rows)


def write_stations_csv(stations: set[str]) -> None:
    with open(OUTPUT_STATIONS_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=CSV_DELIMITER)
        w.writerow(["name"])
        for name in sorted(stations):
            w.writerow([name])


def main() -> None:
    if not INPUT_FILE.exists():
        print(f"[ERR] Fichier introuvable: {INPUT_FILE}", file=sys.stderr)
        sys.exit(1)

    lines = INPUT_FILE.read_text(encoding="utf-8").splitlines()
    excluded_stations = load_excluded_stations()

    rows, stations, excluded_count, unparsed_count = parse_lines(
        lines, excluded_stations
    )

    write_price_csv(rows)
    write_stations_csv(stations)

    print(f"OK -> {OUTPUT_PRICE_CSV} ({len(rows)} lignes)")
    print(f"OK -> {OUTPUT_STATIONS_CSV} ({len(stations)} gares)")
    print(f"Info -> lignes exclues: {excluded_count}")
    print(f"Info -> lignes non reconnues: {unparsed_count}")


if __name__ == "__main__":
    main()
