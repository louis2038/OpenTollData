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
OUTPUT_STATIONS_CSV = BASE_DIR / "COFIROUTE_names.csv"
OUTPUT_OPEN_CSV = BASE_DIR / "COFIROUTE_data_price_open_2026.csv"

CSV_DELIMITER = ";"
DISTANCE_DEFAULT = ""

# Transformation manuelle d'un nom normalise vers un autre.
TRANSFORME_NAME = [
    {"from": "ANGERS CORZE", "to": "PEAGE DE CORZE"},
    {"from": "AUVOURS LE MANS ZI SUD", "to": "AVOURS"},
    {"from": "BARRIERE DE MONTREUIL AUX LIONS", "to": "PEAGE DE MONTREUIL AUX LIONS"},
    {"from": "BEAULIEU", "to": "PEAGE DE BEAULIEU S LAYON"},
    {"from": "BEAUMONT", "to": "PEAGE DE BEAUMONT"},
    {"from": "BEAUMONT SUR SARTHE", "to": "MARESCHE"},
]

# Noms de gares a exclure (normalisation appliquee automatiquement).
EXCLUDED_STATIONS = {"ANGERS"}

# Regles manuelles de generation du CSV open.
# Format de chaque regle:
# {
#     "from": "GARE DE DEPART",
#     "to": "GARE D'ARRIVEE",
#     "open_name": "NOM DE LA GARE OPEN"
# }
#
# Si la gare "to" n'existe pas exactement, un fallback essaie un match
# de type "startswith" (ex: "ANGERS" trouvera "ANGERS CORZE").
MANUAL_OPEN_RULES = [
    {
        "from": "ANCENIS",
        "to": "ANGERS",
        "open_name": "ANCENIS DIR ANGERS",
    },
    {
        "from": "ANCENIS",
        "to": "NANTES",
        "open_name": "ANCENIS DIR NANTES",
    },
    {
        "from": "NANTES",
        "to": "ANGERS",
        "open_name": "ANCENIS PEAGE",
    },
    {
        "from": "BEAUPREAU SAINT GERMAIN",
        "to": "ANGERS",
        "open_name": "BEAUPREAU SAINT GERMAIN",
    },
    {
        "from": "SAINT JEAN DE LINIERES",
        "to": "ANGERS",
        "open_name": "SAINT JEAN DE LINIERES",
    },
    {
        "from": "VIEILLEVILLE",
        "to": "NANTES",
        "open_name": "VIEILLEVILLE",
    },
]


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


def apply_name_transform(name: str) -> str:
    from_name = normalize_name(TRANSFORME_NAME.get("from", ""))
    to_name = normalize_name(TRANSFORME_NAME.get("to", ""))
    if from_name and to_name and name == from_name:
        return to_name
    return name


def load_excluded_stations() -> set[str]:
    return {normalize_name(name) for name in EXCLUDED_STATIONS if name.strip()}


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
        name_from = apply_name_transform(normalize_name(d["name_from"]))
        name_to = apply_name_transform(normalize_name(d["name_to"]))

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


def build_close_price_lookup(rows: list[list[str]]) -> dict[tuple[str, str], list[str]]:
    lookup: dict[tuple[str, str], list[str]] = {}
    duplicates = 0

    for row in rows:
        key = (row[0], row[1])
        if key in lookup:
            duplicates += 1
            continue
        lookup[key] = row

    if duplicates:
        print(
            f"[WARN] {duplicates} doublon(s) from/to detecte(s) dans les donnees close",
            file=sys.stderr,
        )

    return lookup


def generate_open_rows_from_manual_rules(
    close_lookup: dict[tuple[str, str], list[str]],
) -> tuple[list[list[str]], int]:
    open_rows: list[list[str]] = []
    missing_rules = 0

    # Index de fallback: from -> liste de tous les to dispo
    to_by_from: dict[str, list[str]] = {}
    for from_name, to_name in close_lookup:
        to_by_from.setdefault(from_name, []).append(to_name)

    for rule in MANUAL_OPEN_RULES:
        if "from" not in rule or "to" not in rule or "open_name" not in rule:
            print(f"[WARN] Regle open invalide: {rule}", file=sys.stderr)
            missing_rules += 1
            continue

        from_norm = apply_name_transform(normalize_name(rule["from"]))
        to_norm = apply_name_transform(normalize_name(rule["to"]))
        open_name = apply_name_transform(normalize_name(rule["open_name"]))

        close_row = close_lookup.get((from_norm, to_norm))

        if close_row is None:
            candidates = [
                candidate_to
                for candidate_to in to_by_from.get(from_norm, [])
                if candidate_to.startswith(to_norm)
            ]

            if len(candidates) == 1:
                close_row = close_lookup[(from_norm, candidates[0])]
            elif len(candidates) > 1:
                print(
                    f"[WARN] Regle open ambigue: from='{from_norm}' to='{to_norm}' -> {len(candidates)} candidats",
                    file=sys.stderr,
                )
                missing_rules += 1
                continue

        if close_row is None:
            print(
                f"[WARN] Regle open introuvable dans close: from='{from_norm}' to='{to_norm}'",
                file=sys.stderr,
            )
            missing_rules += 1
            continue

        open_rows.append(
            [
                open_name,
                DISTANCE_DEFAULT,
                close_row[3],
                close_row[4],
                close_row[5],
                close_row[6],
                close_row[7],
            ]
        )

    return open_rows, missing_rules


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


def write_open_csv(rows: list[list[str]]) -> None:
    with open(OUTPUT_OPEN_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=CSV_DELIMITER)
        w.writerow(
            ["name", "distance", "price1", "price2", "price3", "price4", "price5"]
        )
        w.writerows(rows)


def main() -> None:
    if not INPUT_FILE.exists():
        print(f"[ERR] Fichier introuvable: {INPUT_FILE}", file=sys.stderr)
        sys.exit(1)

    lines = INPUT_FILE.read_text(encoding="utf-8").splitlines()
    excluded_stations = load_excluded_stations()

    rows, stations, excluded_count, unparsed_count = parse_lines(
        lines, excluded_stations
    )
    all_rows, _, _, _ = parse_lines(lines, set())
    close_lookup = build_close_price_lookup(all_rows)
    open_rows, missing_open_rules = generate_open_rows_from_manual_rules(close_lookup)

    write_price_csv(rows)
    write_stations_csv(stations)
    write_open_csv(open_rows)

    print(f"OK -> {OUTPUT_PRICE_CSV} ({len(rows)} lignes)")
    print(f"OK -> {OUTPUT_STATIONS_CSV} ({len(stations)} gares)")
    print(f"OK -> {OUTPUT_OPEN_CSV} ({len(open_rows)} lignes)")
    print(f"Info -> lignes exclues: {excluded_count}")
    print(f"Info -> lignes non reconnues: {unparsed_count}")
    print(f"Info -> regles open non resolues: {missing_open_rules}")


if __name__ == "__main__":
    main()
