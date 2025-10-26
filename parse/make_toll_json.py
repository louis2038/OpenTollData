
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build a toll network JSON from three CSVs and validate consistency.

Inputs:
  - price_close CSV (semicolon-separated): name_from;name_to;distance;price1;...;price5
  - price_open  CSV (semicolon-separated with decimal commas possible): name;distance;price1;...;price5
  - toll_info   CSV (semicolon-separated): name;osm_name;operator_ref;lat;lon;nbs_booth;booth_node_id;booth_way_id;type;operator_osm

Validation performed:
  - Every name present in price_close or price_open must exist in toll_info.
  - Names used in price_close must have type == "close" in toll_info.
  - Names used in price_open  must have type == "open"  in toll_info.
  - Basic numeric parsing checks for distances/prices.
If any error is found, a detailed report is printed and the program exits with code 1.

Output JSON structure:
{
    "date": "DD/MM/YYYY",
    "version": "<version>",
    "name": "<name>",
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
import os
import sys
from collections import defaultdict, deque

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
    """Accept both '3.5' and '3,5', return float. Empty -> None. Raise on bad format."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = _strip(value)
    if s == "" or s is None:
        return None
    # replace decimal comma by dot
    s = s.replace(",", ".")
    return float(s)

def _to_str_number(value):
    """Serialize a float as a compact string, without trailing zeros (e.g., 3.5 -> '3.5', 5.0 -> '5')."""
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (int,)):
        return str(value)
    # float
    s = f"{value:.10f}".rstrip("0").rstrip(".")
    return s if s else "0"

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
    edges = []  # list of dicts: {from, to, distance, prices{class_1..class_5}}
    errors = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        required = ["name_from", "name_to", "distance", "price1", "price2", "price3", "price4", "price5"]
        missing = [c for c in required if c not in reader.fieldnames]
        if missing:
            errors.append(f"[close] Colonnes manquantes: {missing}")
            return edges, errors
        for i, row in enumerate(reader, start=2):
            frm = _strip(row["name_from"])
            to  = _strip(row["name_to"])
            try:
                dist = _to_float(row["distance"])
                p1 = _to_float(row["price1"]); p2 = _to_float(row["price2"]); p3 = _to_float(row["price3"])
                p4 = _to_float(row["price4"]); p5 = _to_float(row["price5"])
            except Exception as ex:
                errors.append(f"[close] Ligne {i}: erreur de parsing numérique ({ex}).")
                continue
            if not frm or not to:
                errors.append(f"[close] Ligne {i}: name_from/name_to manquant.")
                continue
            if dist is None:
                errors.append(f"[close] Ligne {i}: distance manquante.")
                continue
            prices = {
                "class_1": _to_str_number(p1),
                "class_2": _to_str_number(p2),
                "class_3": _to_str_number(p3),
                "class_4": _to_str_number(p4),
                "class_5": _to_str_number(p5),
            }
            edges.append({
                "from": frm,
                "to": to,
                "distance": dist,
                "price": prices
            })
    return edges, errors

def read_price_open(path):
    rows = {}  # name -> {distance, price{class_1..class_5}}
    errors = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        required = ["name", "distance", "price1", "price2", "price3", "price4", "price5"]
        missing = [c for c in required if c not in reader.fieldnames]
        if missing:
            errors.append(f"[open] Colonnes manquantes: {missing}")
            return rows, errors
        for i, row in enumerate(reader, start=2):
            name = _strip(row["name"])
            if not name:
                errors.append(f"[open] Ligne {i}: name manquant.")
                continue
            try:
                dist = _to_float(row["distance"])
                p1 = _to_float(row["price1"]); p2 = _to_float(row["price2"]); p3 = _to_float(row["price3"])
                p4 = _to_float(row["price4"]); p5 = _to_float(row["price5"])
            except Exception as ex:
                errors.append(f"[open] Ligne {i}: erreur de parsing numérique ({ex}).")
                continue
            if dist is None:
                errors.append(f"[open] Ligne {i}: distance manquante.")
                continue
            rows[name] = {
                "distance": dist,
                "price": {
                    "class_1": _to_str_number(p1),
                    "class_2": _to_str_number(p2),
                    "class_3": _to_str_number(p3),
                    "class_4": _to_str_number(p4),
                    "class_5": _to_str_number(p5),
                }
            }
    return rows, errors

def validate_cross(info, close_edges, open_rows):
    errors = []
    warnings = []

    # Known names and types
    known = set(info.keys())
    type_by_name = {k: v.get("type") for k, v in info.items()}

    # Validate close
    for e in close_edges:
        for nm in (e["from"], e["to"]):
            if nm not in known:
                errors.append(f"[close] Nom inconnu dans toll_info: '{nm}'")
            else:
                if type_by_name[nm] != "close":
                    errors.append(f"[close] Type attendu 'close' pour '{nm}', trouvé '{type_by_name[nm]}'")

    # Validate open
    for nm in open_rows.keys():
        if nm not in known:
            errors.append(f"[open] Nom inconnu dans toll_info: '{nm}'")
        else:
            if type_by_name[nm] != "open":
                errors.append(f"[open] Type attendu 'open' pour '{nm}', trouvé '{type_by_name[nm]}'")

    return errors, warnings

def connected_components(nodes, edges):
    """Undirected graph components using close edges (connections exist if an edge in either direction is present)."""
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
        # BFS
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
    """Return list of components; each with tolls and directional connection mapping"""
    # Nodes involved in close edges only
    nodes = sorted(set([e["from"] for e in close_edges]) | set([e["to"] for e in close_edges]))
    comps = connected_components(nodes, close_edges)

    # Map to index for naming
    networks = []
    # Build adjacency mapping per component, with directional connections as given in CSV
    # We'll group edges per 'from' then 'to'
    edges_by_from = defaultdict(list)
    for e in close_edges:
        edges_by_from[e["from"]].append(e)

    for idx, comp in enumerate(comps, start=1):
        connection = {}
        for frm in comp:
            # Only include connections to nodes within the same component
            outs = {}
            for e in edges_by_from.get(frm, []):
                to = e["to"]
                if to not in comp:
                    continue
                outs[to] = {
                    "distance": _to_str_number(e["distance"]),
                    "price": e["price"]
                }
            if outs:
                connection[frm] = outs
            else:
                # still include node with empty dict to be explicit
                connection[frm] = {}
        networks.append({
            "network_name": f"component_{idx}",
            "tolls": comp,
            "connection": connection
        })
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
            "ways_id": rec.get("ways_id") or []
        }
    return out

def main():
    ap = argparse.ArgumentParser(description="Validate toll CSVs and build JSON.")
    ap.add_argument("--close", required=True, help="Path to AREA_data_price_close.csv")
    ap.add_argument("--open", required=True, help="Path to AREA_data_price_open.csv")
    ap.add_argument("--info", required=True, help="Path to AREA_toll_info.csv")
    ap.add_argument("--out", default="toll_network.json", help="Output JSON path")
    ap.add_argument("--version", default="1.0")
    ap.add_argument("--name", default="price_format")
    ap.add_argument("--currency", default="EUR")
    args = ap.parse_args()

    info, operators = read_toll_info(args.info)
    close_edges, close_errs = read_price_close(args.close)
    open_rows, open_errs = read_price_open(args.open)

    errs = close_errs + open_errs
    cross_errs, cross_warns = validate_cross(info, close_edges, open_rows)
    errs += cross_errs

    # If errors, print them and exit non-zero
    if errs:
        print("❌ Incompatibilités / erreurs détectées:\n", file=sys.stderr)
        for e in errs:
            print(" - " + e, file=sys.stderr)
        if cross_warns:
            print("\n⚠️  Avertissements:", file=sys.stderr)
            for w in cross_warns:
                print(" - " + w, file=sys.stderr)
        sys.exit(1)

    # Build the JSON
    today = dt.date.today().strftime("%d/%m/%Y")
    list_of_toll = sorted(info.keys())
    networks = build_networks_from_close(close_edges)
    toll_description = build_toll_description(info)

    # Prepare open_toll_price (stringify numbers)
    open_toll_price = {}
    for name, rec in open_rows.items():
        open_toll_price[name] = {
            "distance": _to_str_number(rec["distance"]),
            "price": {k: (v if v is not None else "") for k, v in rec["price"].items()}
        }

    # Compose final JSON
    payload = {
        "date": today,
        "version": args.version,
        "name": args.name,
        "list_of_operator": operators,
        "list_of_toll": list_of_toll,
        "currency": args.currency,
        "networks": networks,
        "toll_description": toll_description,
        "open_toll_price": open_toll_price,
    }

    # Write
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=4)

    # Summary
    print(f"✅ Fichiers compatibles. JSON écrit dans: {args.out}")
    print(f"- Nombre de péages: {len(list_of_toll)}")
    print(f"- Nombre de réseaux (composantes connexes): {len(networks)}")
    print(f"- Opérateurs détectés: {', '.join(operators) if operators else '(aucun)'}")

if __name__ == "__main__":
    main()
