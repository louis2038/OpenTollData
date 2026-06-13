#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2025-2026 Louis TRIOULEYRE-ROBERJOT
# This file is part of TollData - Open French Highway Toll Database
"""
Build a toll network JSON from three CSVs.

Validation is delegated entirely to validate_triplet.py which is called
before any JSON generation.  If you need to add or modify a validation
rule, edit validate_triplet.py only.

Inputs:
  - price_close CSV (semicolon-separated): name_from;name_to;distance;price1;...;price5
  - price_open  CSV (semicolon-separated with decimal commas possible): name;distance;price1;...;price5
  - toll_info   CSV (semicolon-separated): name;osm_name;operator_ref;lat;lon;nbs_booth;booth_node_id;booth_way_id;type;operator_osm

Output JSON structure:
{
    "date": "DD/MM/YYYY",
    "version": "<version>",
    "name": "<name>",
    "license": {
        "data": "ODbL-1.0",
        "url": "https://opendatacommons.org/licenses/odbl/1-0/"
    },
    "copyright": "(c) 2025-2026 Louis TRIOULEYRE-ROBERJOT",
    "list_of_operator": [...],
    "list_of_toll": [...],
    "currency": "<currency>",

    "networks": [
        {
            "network_name": "component_1",
            "tolls": [...],
            "connection": {
                "TOLL_A": {
                    "TOLL_B": {
                        "distance": "X.Y",
                        "price": {"class_1": "...", ..., "class_5": "..."}
                    },
                    ...
                },
                ...
            }
        },
        ...
    ],

    "toll_description": {
        "TOLL_NAME": {
            "operator_ref": "...",
            "lat": "...",
            "lon": "...",
            "operator": "...",
            "type": "open|close",
            "node_id": [...],
            "ways_id": [...]
        },
        ...
    },

    "open_toll_price": {
        "OPEN_TOLL": {
            "distance": "...",
            "price": {"class_1": "...", ..., "class_5": "..."}
        },
        ...
    }
}

Usage:
  python make_toll_json.py \
      --close AREA_data_price_close.csv \
      --open  AREA_data_price_open.csv  \
      --info  AREA_toll_info.csv        \
      --out   output.json               \
      --version 1.0 --name price_format --currency EUR

"""

import argparse
import ast
import csv
import datetime as dt
import json
import math
import sys
from collections import defaultdict, deque

from validate_triplet import TripletValidationError, validate_triplet


# ───────────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────────


def _strip(s):
    return s.strip() if isinstance(s, str) else s


def _as_list_from_brackets(s):
    """Parse a bracketed list like '[1, 2, 3]' into a list of strings. Empty/None -> []."""
    s = _strip(s)
    if not s:
        return []
    try:
        val = ast.literal_eval(s)
        if isinstance(val, (list, tuple)):
            return [str(x) for x in val]
        # If it's a single value, wrap it
        return [str(val)]
    except Exception:
        # Fallback: remove brackets and split by comma
        s2 = s.strip().strip("[]").strip()
        if not s2:
            return []
        return [x.strip() for x in s2.split(",")]


def _to_float(value):
    """Accept both '3.5' and '3,5', return float. Empty -> None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = _strip(value)
    if s == "" or s is None:
        return None
    s = s.replace(",", ".")
    return float(s)


def _to_str_number(value):
    """Serialize a float as a compact string, without trailing zeros."""
    if value is None or (
        isinstance(value, float) and (math.isnan(value) or math.isinf(value))
    ):
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (int,)):
        return str(value)
    s = f"{value:.10f}".rstrip("0").rstrip(".")
    return s if s else "0"


# ───────────────────────────────────────────────────────────────────
# CSV readers (data extraction only, no validation)
# ───────────────────────────────────────────────────────────────────


def read_toll_info(path):
    info = {}
    operators = set()
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            name = _strip(row.get("name"))
            if not name:
                continue
            rec = {
                "operator_ref": _strip(row.get("operator_ref")),
                "lat": _strip(row.get("lat")),
                "lon": _strip(row.get("lon")),
                "operator": _strip(row.get("operator_osm")),
                "type": _strip(row.get("type")),
                "node_id": _as_list_from_brackets(row.get("booth_node_id")),
                "ways_id": _as_list_from_brackets(row.get("booth_way_id")),
            }
            info[name] = rec
            if rec["operator"]:
                operators.add(rec["operator"])
    return info, sorted(operators)


def read_price_close(path):
    edges = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            frm = _strip(row["name_from"])
            to = _strip(row["name_to"])
            dist = _to_float(row["distance"])
            prices = {
                "class_1": _to_str_number(_to_float(row["price1"])),
                "class_2": _to_str_number(_to_float(row["price2"])),
                "class_3": _to_str_number(_to_float(row["price3"])),
                "class_4": _to_str_number(_to_float(row["price4"])),
                "class_5": _to_str_number(_to_float(row["price5"])),
            }
            edges.append({"from": frm, "to": to, "distance": dist, "price": prices})
    return edges


def read_price_open(path):
    rows = {}
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            name = _strip(row["name"])
            dist = _to_float(row["distance"])
            prices = {
                "class_1": _to_str_number(_to_float(row["price1"])),
                "class_2": _to_str_number(_to_float(row["price2"])),
                "class_3": _to_str_number(_to_float(row["price3"])),
                "class_4": _to_str_number(_to_float(row["price4"])),
                "class_5": _to_str_number(_to_float(row["price5"])),
            }
            rows[name] = {"distance": dist, "price": prices}
    return rows


# ───────────────────────────────────────────────────────────────────
# Graph / network building
# ───────────────────────────────────────────────────────────────────


def connected_components(nodes, edges):
    """Undirected graph components using BFS."""
    adj = defaultdict(set)
    for e in edges:
        a, b = e["from"], e["to"]
        adj[a].add(b)
        adj[b].add(a)
    seen = set()
    comps = []
    for n in nodes:
        if n in seen:
            continue
        q = deque([n])
        cur = []
        seen.add(n)
        while q:
            u = q.popleft()
            cur.append(u)
            for v in adj[u]:
                if v not in seen:
                    seen.add(v)
                    q.append(v)
        comps.append(sorted(cur))
    return comps


def build_networks_from_close(close_edges):
    """Return list of components with tolls and directional connection mapping."""
    nodes = sorted(
        set([e["from"] for e in close_edges]) | set([e["to"] for e in close_edges])
    )
    comps = connected_components(nodes, close_edges)

    edges_by_from = defaultdict(list)
    for e in close_edges:
        edges_by_from[e["from"]].append(e)

    networks = []
    for idx, comp in enumerate(comps, start=1):
        connection = {}
        for frm in comp:
            outs = {}
            for e in edges_by_from.get(frm, []):
                to = e["to"]
                if to not in comp:
                    continue
                outs[to] = {
                    "distance": _to_str_number(e["distance"])
                    if e["distance"] is not None
                    else "",
                    "price": e["price"],
                }
            if outs:
                connection[frm] = outs
            else:
                connection[frm] = {}
        networks.append(
            {
                "network_name": f"component_{idx}",
                "tolls": comp,
                "connection": connection,
            }
        )
    return networks


def build_toll_description(info):
    out = {}
    for name, rec in info.items():
        out[name] = {
            "operator_ref": rec.get("operator_ref") or "",
            "lat": str(rec.get("lat") or ""),
            "lon": str(rec.get("lon") or ""),
            "operator": rec.get("operator") or "",
            "type": rec.get("type") or "",
            "node_id": rec.get("node_id") or [],
            "ways_id": rec.get("ways_id") or [],
        }
    return out


# ───────────────────────────────────────────────────────────────────
# Main
# ───────────────────────────────────────────────────────────────────


def main():
    ap = argparse.ArgumentParser(description="Validate toll CSVs and build JSON.")
    ap.add_argument("--close", required=True, help="Path to price_close CSV")
    ap.add_argument("--open", required=True, help="Path to price_open CSV")
    ap.add_argument("--info", required=True, help="Path to toll_info CSV")
    ap.add_argument("--out", default="toll_network.json", help="Output JSON path")
    ap.add_argument("--version", default="1.0")
    ap.add_argument("--name", default="price_format")
    ap.add_argument("--currency", default="EUR")
    args = ap.parse_args()

    # ── Validation (single source of truth: validate_triplet.py) ──
    try:
        validate_triplet(args.close, args.open, args.info, verbose=True)
    except TripletValidationError as e:
        print(f"\n{e}\n", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"\n  ERREUR: {e}\n", file=sys.stderr)
        sys.exit(1)

    # ── Read data for JSON building ──────────────────────────────
    info, operators = read_toll_info(args.info)
    close_edges = read_price_close(args.close)
    open_rows = read_price_open(args.open)

    # ── Build the JSON ───────────────────────────────────────────
    today = dt.date.today().strftime("%d/%m/%Y")
    list_of_toll = sorted(info.keys())
    networks = build_networks_from_close(close_edges)
    toll_description = build_toll_description(info)

    open_toll_price = {}
    for name, rec in open_rows.items():
        open_toll_price[name] = {
            "distance": _to_str_number(rec["distance"])
            if rec["distance"] is not None
            else "",
            "price": {k: (v if v is not None else "") for k, v in rec["price"].items()},
        }

    payload = {
        "date": today,
        "version": args.version,
        "name": args.name,
        "license": {
            "data": "ODbL-1.0",
            "url": "https://opendatacommons.org/licenses/odbl/1-0/",
        },
        "copyright": "(c) 2025-2026 Louis TRIOULEYRE-ROBERJOT",
        "list_of_operator": operators,
        "list_of_toll": list_of_toll,
        "currency": args.currency,
        "networks": networks,
        "toll_description": toll_description,
        "open_toll_price": open_toll_price,
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=4)

    print(f"\n  Fichiers compatibles. JSON ecrit dans: {args.out}")
    print(f"  - Nombre de peages: {len(list_of_toll)}")
    print(f"  - Nombre de reseaux (composantes connexes): {len(networks)}")
    print(
        f"  - Operateurs detectes: {', '.join(operators) if operators else '(aucun)'}"
    )


if __name__ == "__main__":
    main()
