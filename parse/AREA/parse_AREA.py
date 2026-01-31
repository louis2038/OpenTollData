#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2025-2026 Louis TRIOULEYRE-ROBERJOT
# This file is part of TollData - Open French Highway Toll Database

import re
import csv
import sys
from pathlib import Path

import re
import unicodedata

def normalize_name(s: str) -> str:
    if not s:
        return ""
    # Normalisation Unicode
    s = unicodedata.normalize("NFKC", s)
    # Retire les diacritiques (accents)
    s = "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )
    # Remplace tout ce qui n'est PAS lettre ou chiffre par un espace
    s = re.sub(r"[^A-Za-z0-9]", " ", s)
    # Remplace plusieurs espaces par un seul
    s = re.sub(r"\s+", " ", s)
    # Trim
    s = s.strip()
    # Uppercase
    return s.upper()

LINE_RE = re.compile(
    r"""^\s*
    (?P<code_from>\d+)\s+
    (?P<name_from>.+?)\s+
    (?P<code_to>\d+)\s+
    (?P<name_to>.+?)\s+
    (?P<distance>\d+,\d{2})\s+
    (?P<price1>\d+,\d{2})\s*€?\s+
    (?P<price2>\d+,\d{2})\s*€?\s+
    (?P<price3>\d+,\d{2})\s*€?\s+
    (?P<price4>\d+,\d{2})\s*€?\s+
    (?P<price5>\d+,\d{2})\s*€?\s*
    $""",
    re.VERBOSE
)

def fr_to_float_str(x: str) -> str:
    return x.replace(",", ".")

def parse_lines(lines):
    rows = []
    stations = {}
    for i, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line:
            continue
        m = LINE_RE.match(line)
        if not m:
            print(f"[WARN] Ligne {i} non reconnue : {line}", file=sys.stderr)
            continue
        d = m.groupdict()
        code_from, name_from = d["code_from"], " ".join(d["name_from"].split())
        code_to, name_to   = d["code_to"], " ".join(d["name_to"].split())

        # Ajouter aux résultats principaux
        rows.append([
            normalize_name(name_from),
            normalize_name(name_to),
            fr_to_float_str(d["distance"]),
            fr_to_float_str(d["price1"]),
            fr_to_float_str(d["price2"]),
            fr_to_float_str(d["price3"]),
            fr_to_float_str(d["price4"]),
            fr_to_float_str(d["price5"]),
        ])

        # Collecter les gares (évite doublons avec dict)
        stations[code_from] = name_from
        stations[code_to] = name_to

    return rows, stations

def main():
    import argparse
    p = argparse.ArgumentParser(description="Parser de tarifs -> CSV (10 colonnes).")
    p.add_argument("input", help="Fichier texte source (UTF-8). Utilisez '-' pour stdin.")
    p.add_argument("-o", "--output", default="sortie.csv", help="Fichier CSV de sortie principal")
    p.add_argument("--delimiter", default=",", help="Délimiteur CSV (par défaut: ','). Ex: ';' pour Excel FR.")
    p.add_argument("--stations-only", metavar="FICHIER", help="Créer aussi un CSV avec seulement les gares (code,name)")
    args = p.parse_args()

    if args.input == "-":
        lines = sys.stdin.read().splitlines()
    else:
        lines = Path(args.input).read_text(encoding="utf-8").splitlines()

    rows, stations = parse_lines(lines)

    header = ["name_from", "name_to",
              "distance", "price1", "price2", "price3", "price4", "price5"]

    with open(args.output, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=args.delimiter)
        w.writerow(header)
        w.writerows(rows)

    print(f"OK → {args.output} ({len(rows)} lignes)")

    # Fichier des gares
    if args.stations_only:
        with open(args.stations_only, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, delimiter=args.delimiter)
            w.writerow(["name"])
            for code, name in sorted(stations.items()):
                w.writerow([normalize_name(name)])
        print(f"OK → {args.stations_only} ({len(stations)} gares)")

if __name__ == "__main__":
    main()
