#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2025-2026 contributors
# This file is part of TollData - Open French Highway Toll Database
"""
Parse Sanef / SAPN brochure PDFs (triangular matrices per vehicle class).

Sources (layout PDF → pdftotext -layout):
  SANEF/raw_data/SANEF_tarifs_2026.pdf
  SAPN/raw_data/SAPN_tarifs_2026.pdf

Outputs (per operator directory):
  <OP>_data_price_close_2026.csv
  <OP>_data_price_open_2026.csv
  <OP>_toll_info.csv
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

PRICE_RE = re.compile(r"^\d+,\d+$")
SKIP_RE = re.compile(
    r"^(TARIFS DE PEAGE|TAUX DE TVA|Tarifs de péage|\d{4}$|1er février|"
    r"Pour information|http://|https://|TARIF DE BASE|TARIF REDUIT|"
    r"Le tarif |PONT DE NORMANDIE|A150 \(ALBEA\)|MODULATION)",
    re.I,
)


def normalize_name(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )
    s = re.sub(r"[^A-Za-z0-9]", " ", s)
    s = re.sub(r"\s+", " ", s).strip().upper()
    return s


def clean_display_name(name: str) -> str:
    name = re.sub(r"\s+", " ", name).strip(" -")
    # "LE HAVRE N°5 / A131" → "LE HAVRE N°5"
    name = re.sub(r"\s*/\s*A\d{1,3}(\s+[A-Z0-9]+)?$", "", name, flags=re.I)
    name = re.sub(r"\s+A\d{1,3}(\s+(NORD|SUD|EST|OUEST))?$", "", name, flags=re.I)
    name = name.strip(" -/")
    return name


def is_price(tok: str) -> bool:
    return bool(PRICE_RE.match(tok))


def pdf_to_text(pdf: Path) -> str:
    proc = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout


def parse_class_page(page: str) -> list[dict]:
    """Parse one CLASSE page into matrices + open barriers."""
    matrices: list[dict] = []
    stations: list[str] = []
    prices: dict[tuple[int, int], float] = {}
    opens: list[tuple[str, float]] = []
    label = ""
    carry_first: str | None = None
    # Survives flush() when AUTOROUTES header follows "GARE + prix" (Calais, Boulogne Est…).
    section_seed: str | None = None

    def flush() -> None:
        nonlocal stations, prices, opens, label, carry_first
        if len(stations) >= 2 and prices:
            matrices.append(
                {
                    "label": label,
                    "stations": stations[:],
                    "prices": dict(prices),
                    "opens": opens[:],
                }
            )
        elif opens and not prices:
            matrices.append(
                {
                    "label": label or "open",
                    "stations": [],
                    "prices": {},
                    "opens": opens[:],
                }
            )
        stations, prices, opens = [], {}, []
        label = ""

    for raw in page.splitlines():
        ln = raw.strip()
        if not ln:
            continue
        if SKIP_RE.search(ln) and "péage" not in ln.lower():
            continue
        if re.match(r"^AUTOROUTES?\b", ln, re.I):
            seed = section_seed or carry_first
            section_seed = None
            carry_first = None
            flush()
            label = ln
            if seed:
                stations.append(seed)
            continue

        tokens = ln.split()
        if len(tokens) == 1 and is_price(tokens[0]):
            val = float(tokens[0].replace(",", "."))
            if carry_first:
                # Barrier fee + seed for the following closed matrix.
                opens.append((carry_first, val))
                section_seed = carry_first
                carry_first = None
            continue

        n_prices = 0
        while n_prices < len(tokens) and is_price(tokens[n_prices]):
            n_prices += 1
        name_tokens = tokens[n_prices:]

        # Footer open barriers: "NAME 1,3 NAME2 0,9" (price after name)
        if n_prices == 0:
            trailing = re.findall(
                r"([A-ZÀ-Ü0-9][^;]*?)\s+(\d+,\d+)(?=\s+[A-ZÀ-Ü]|\s*$)",
                ln,
            )
            if trailing and sum(1 for _n, p in trailing if is_price(p)) >= 1:
                # Only treat as footer if multiple name/price OR looks like open list
                if len(trailing) >= 2 or re.search(r"N°\d+", ln):
                    if stations and prices:
                        flush()
                    for nm, pv in trailing:
                        nm_c = clean_display_name(nm)
                        if len(nm_c) < 3:
                            continue
                        opens.append((nm_c, float(pv.replace(",", "."))))
                    continue

        if not name_tokens:
            continue

        name = clean_display_name(" ".join(name_tokens))
        if len(name) < 2:
            continue
        if name.startswith("(") and "péage" in name.lower() and stations:
            stations[-1] = clean_display_name(stations[-1] + " " + name)
            continue
        if re.fullmatch(r"A\d{1,3}", name, re.I):
            continue

        if n_prices == 0:
            # Station alone.
            if stations and prices:
                # Nouvelle gare d'entrée (ex. CALAIS (péage de …)) → nouvelle matrice.
                # Sinon continuation (ex. TANCARVILLE, BONNIÈRES sur A13 SAPN).
                if re.search(r"péage\s+de\b", name, re.I):
                    flush()
                    carry_first = name
                    continue
                stations.append(name)
                continue
            if stations and not prices:
                continue
            carry_first = name
            continue

        if carry_first and not stations:
            stations.append(carry_first)
            carry_first = None
        if not stations:
            continue

        if n_prices != len(stations):
            # Soft accept when off-by-one after messy PDF lines
            if n_prices == 0:
                continue
            take = min(n_prices, len(stations))
            if take < 1:
                continue
        else:
            take = n_prices

        idx = len(stations)
        stations.append(name)
        for j in range(take):
            pv = float(tokens[j].replace(",", "."))
            prices[(idx, j)] = pv
            prices[(j, idx)] = pv
        carry_first = None

    flush()
    return matrices


def parse_sapn_a14_opens(text: str) -> list[dict]:
    """A14 Montesson / Chambourcy are flat open barriers (base fare)."""
    rows: list[dict] = []
    # One block per class page
    for m in re.finditer(
        r"CLASSE\s+(\d)([\s\S]*?)(?=CLASSE\s+\d|\Z)",
        text,
    ):
        cls = int(m.group(1))
        block = m.group(2)
        if "AUTOROUTE A14" not in block and "PEAGE DE MONTESSON" not in block:
            continue
        mont = re.search(
            r"PEAGE DE MONTESSON\s+TARIF DE BASE\s+(\d+,\d+)",
            block,
            re.I,
        )
        cham = re.search(r"PEAGE DE CHAMBOURCY\s+(\d+,\d+)", block, re.I)
        if mont:
            rows.append(("PEAGE DE MONTESSON", cls, float(mont.group(1).replace(",", "."))))
        if cham:
            rows.append(("PEAGE DE CHAMBOURCY", cls, float(cham.group(1).replace(",", "."))))
    merged: dict[str, list[float | None]] = {}
    for name, cls, pv in rows:
        merged.setdefault(name, [None] * 5)
        merged[name][cls - 1] = pv
    out = []
    for name, prices in merged.items():
        out.append(
            {
                "name": name,
                "distance": "",
                "price1": "" if prices[0] is None else f"{prices[0]:.2f}",
                "price2": "" if prices[1] is None else f"{prices[1]:.2f}",
                "price3": "" if prices[2] is None else f"{prices[2]:.2f}",
                "price4": "" if prices[3] is None else f"{prices[3]:.2f}",
                "price5": "" if prices[4] is None else f"{prices[4]:.2f}",
            }
        )
    return out


def extract_operator(
    pdf: Path, operator_osm: str
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Returns (close_rows, open_rows, toll_info_rows) dict rows.
    close_rows: name_from, name_to, distance, price1..price5
    """
    text = pdf_to_text(pdf)
    pages = text.split("\x0c")

    # class_num -> list of matrices
    by_class: dict[int, list[dict]] = {}
    for page in pages:
        m = re.search(r"CLASSE\s+(\d)", page)
        if not m:
            continue
        cls = int(m.group(1))
        if cls < 1 or cls > 5:
            continue
        by_class[cls] = parse_class_page(page)

    if not by_class:
        raise SystemExit(f"Aucune page CLASSE trouvée dans {pdf}")

    # Merge prices keyed by (from_norm, to_norm) -> [p1..p5]
    pair_prices: dict[tuple[str, str], list[float | None]] = {}
    open_by_name: dict[str, list[float | None]] = {}
    display_names: dict[str, str] = {}

    def ensure_pair(a: str, b: str) -> list[float | None]:
        key = (a, b) if a <= b else (b, a)
        # store directed as well for CSV both ways like other operators
        if (a, b) not in pair_prices:
            pair_prices[(a, b)] = [None, None, None, None, None]
        if (b, a) not in pair_prices:
            pair_prices[(b, a)] = [None, None, None, None, None]
        return pair_prices[(a, b)]

    for cls, mats in sorted(by_class.items()):
        for mat in mats:
            stations = mat["stations"]
            norms = [normalize_name(s) for s in stations]
            for s, n in zip(stations, norms):
                if n:
                    display_names[n] = s
            for (i, j), pv in mat["prices"].items():
                if i <= j:
                    continue
                a, b = norms[i], norms[j]
                if not a or not b or a == b:
                    continue
                slot = cls - 1
                pair_prices.setdefault((a, b), [None] * 5)
                pair_prices.setdefault((b, a), [None] * 5)
                pair_prices[(a, b)][slot] = pv
                pair_prices[(b, a)][slot] = pv
            for name, pv in mat["opens"]:
                n = normalize_name(name)
                if not n:
                    continue
                display_names[n] = name
                open_by_name.setdefault(n, [None] * 5)
                open_by_name[n][cls - 1] = pv

    close_rows = []
    for (a, b), prices in sorted(pair_prices.items()):
        if a == b:
            continue
        if all(p is None for p in prices):
            continue
        close_rows.append(
            {
                "name_from": display_names.get(a, a),
                "name_to": display_names.get(b, b),
                "distance": "",
                "price1": "" if prices[0] is None else f"{prices[0]:.2f}",
                "price2": "" if prices[1] is None else f"{prices[1]:.2f}",
                "price3": "" if prices[2] is None else f"{prices[2]:.2f}",
                "price4": "" if prices[3] is None else f"{prices[3]:.2f}",
                "price5": "" if prices[4] is None else f"{prices[4]:.2f}",
            }
        )

    open_rows = []
    for n, prices in sorted(open_by_name.items()):
        open_rows.append(
            {
                "name": display_names.get(n, n),
                "distance": "",
                "price1": "" if prices[0] is None else f"{prices[0]:.2f}",
                "price2": "" if prices[1] is None else f"{prices[1]:.2f}",
                "price3": "" if prices[2] is None else f"{prices[2]:.2f}",
                "price4": "" if prices[3] is None else f"{prices[3]:.2f}",
                "price5": "" if prices[4] is None else f"{prices[4]:.2f}",
            }
        )

    if operator_osm.upper() == "SAPN":
        a14 = parse_sapn_a14_opens(text)
        by_n = {normalize_name(r["name"]): r for r in open_rows}
        for row in a14:
            n = normalize_name(row["name"])
            display_names[n] = row["name"]
            if n in by_n:
                for k in ("price1", "price2", "price3", "price4", "price5"):
                    if row[k]:
                        by_n[n][k] = row[k]
            else:
                open_rows.append(row)
                by_n[n] = row

    # toll_info: closed stations + open barriers
    station_types: dict[str, str] = {}
    for row in close_rows:
        station_types[normalize_name(row["name_from"])] = "close"
        station_types[normalize_name(row["name_to"])] = "close"
    for row in open_rows:
        n = normalize_name(row["name"])
        station_types.setdefault(n, "open")

    # pdf → raw_data → OPERATOR → parse/
    geo_index = _load_peages_geo(pdf.resolve().parents[2] / "peages_all.csv")

    toll_info = []
    for idx, (n, typ) in enumerate(sorted(station_types.items()), start=1):
        display = display_names.get(n, n)
        lat, lon, booth, osm_name = _match_geo(n, display, geo_index)
        toll_info.append(
            {
                "name": display,
                "osm_name": osm_name or display,
                "operator_ref": str(idx),
                "lat": lat,
                "lon": lon,
                "nbs_booth": "",
                "booth_node_id": booth,
                "booth_way_id": "",
                "type": typ,
                "operator_osm": operator_osm,
            }
        )

    return close_rows, open_rows, toll_info


def _load_peages_geo(path: Path) -> list[tuple[str, str, str, str]]:
    """[(norm_osm_name, lat, lon, booth_node_id), ...]"""
    if not path.is_file():
        return []
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    out = []
    for r in rows:
        name = r.get("osm_name") or ""
        lat = (r.get("lat") or "").strip()
        lon = (r.get("lon") or "").strip()
        if not name or not lat or not lon:
            continue
        out.append((normalize_name(name), lat, lon, r.get("booth_node_id") or ""))
    return out


def _match_geo(
    norm: str, display: str, geo_index: list[tuple[str, str, str, str]]
) -> tuple[str, str, str, str]:
    if not geo_index:
        return "", "", "", ""
    stop = {
        "PEAGE",
        "DE",
        "DU",
        "DES",
        "LA",
        "LE",
        "LES",
        "NORD",
        "SUD",
        "EST",
        "OUEST",
        "PARIS",
        "DIR",
    }
    candidates = []
    for gname, lat, lon, booth in geo_index:
        if not gname or len(gname) < 5:
            continue
        if gname == norm:
            candidates.append((0, gname, lat, lon, booth))
            continue
        # Substring only if both sides are specific enough
        if len(gname) >= 6 and (gname in norm or (len(norm) >= 6 and norm in gname)):
            if gname not in stop:
                candidates.append((1, gname, lat, lon, booth))
                continue
        gt = {t for t in gname.split() if t not in stop and len(t) >= 4}
        nt = {t for t in norm.split() if t not in stop and len(t) >= 4}
        inter = gt & nt
        if len(inter) >= 2:
            candidates.append((2, gname, lat, lon, booth))
        elif len(inter) == 1 and max(len(t) for t in inter) >= 7:
            # SETQUES, CHAMANT, BOULOGNE…
            candidates.append((3, gname, lat, lon, booth))
    if not candidates:
        return "", "", "", ""
    candidates.sort()
    _score, gname, lat, lon, booth = candidates[0]
    return lat, lon, booth, gname


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        w.writeheader()
        for row in rows:
            w.writerow(row)


def run_for(
    operator: str,
    pdf: Path,
    out_dir: Path,
    operator_osm: str,
) -> None:
    close_rows, open_rows, toll_info = extract_operator(pdf, operator_osm)
    write_csv(
        out_dir / f"{operator}_data_price_close_2026.csv",
        [
            "name_from",
            "name_to",
            "distance",
            "price1",
            "price2",
            "price3",
            "price4",
            "price5",
        ],
        close_rows,
    )
    write_csv(
        out_dir / f"{operator}_data_price_open_2026.csv",
        ["name", "distance", "price1", "price2", "price3", "price4", "price5"],
        open_rows,
    )
    write_csv(
        out_dir / f"{operator}_toll_info.csv",
        [
            "name",
            "osm_name",
            "operator_ref",
            "lat",
            "lon",
            "nbs_booth",
            "booth_node_id",
            "booth_way_id",
            "type",
            "operator_osm",
        ],
        toll_info,
    )
    print(
        f"[{operator}] close_pairs={len(close_rows)} open={len(open_rows)} "
        f"stations={len(toll_info)} ← {pdf.name}"
    )


def main() -> None:
    root = Path(__file__).resolve().parent
    parse_root = root.parent
    parser = argparse.ArgumentParser(description="Parse Sanef/SAPN toll PDFs")
    parser.add_argument(
        "--operator",
        choices=("SANEF", "SAPN", "ALL"),
        default="ALL",
    )
    args = parser.parse_args()

    jobs = []
    if args.operator in ("SANEF", "ALL"):
        jobs.append(
            (
                "SANEF",
                root / "raw_data" / "SANEF_tarifs_2026.pdf",
                root,
                "Sanef",
            )
        )
    if args.operator in ("SAPN", "ALL"):
        jobs.append(
            (
                "SAPN",
                parse_root / "SAPN" / "raw_data" / "SAPN_tarifs_2026.pdf",
                parse_root / "SAPN",
                "SAPN",
            )
        )

    for operator, pdf, out_dir, osm in jobs:
        if not pdf.is_file():
            print(f"MANQUANT: {pdf}", file=sys.stderr)
            sys.exit(1)
        run_for(operator, pdf, out_dir, osm)


if __name__ == "__main__":
    main()
