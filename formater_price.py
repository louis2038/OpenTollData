#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2025-2026 Louis TRIOULEYRE-ROBERJOT
# This file is part of TollData - Open French Highway Toll Database

import argparse
import csv
import json
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Colonnes attendues (séparateur = ;)
EXPECTED_HEADERS = [
    "code_from", "name_from", "code_to", "name_to",
    "distance", "price1", "price2", "price3", "price4", "price5"
]

def read_semicolon_csv(path: Path) -> List[dict]:
    with path.open("r", encoding="utf-8") as f:
        # Sniffer simple : s'il n'y a pas d'en-tête, on lève une erreur explicite
        header = f.readline().strip()
        f.seek(0)
        reader = csv.DictReader(f, delimiter=';')
        headers_in = [h.strip() for h in reader.fieldnames or []]
        missing = [h for h in EXPECTED_HEADERS if h not in headers_in]
        if missing:
            raise ValueError(
                f"Colonnes manquantes dans {path.name}: {missing}\n"
                f"Colonnes présentes: {headers_in}\n"
                f"Attendu: {EXPECTED_HEADERS}"
            )
        rows = [ {k.strip(): v.strip() for k,v in row.items()} for row in reader ]
    return rows

def build_graph(rows: List[dict]) -> Tuple[Dict[str, Set[str]], Set[Tuple[str, str]]]:
    """
    Graphe non orienté pour les composantes connexes (par noms).
    On garde aussi les arêtes dirigées présentes (origin->dest) pour détecter two_sides.
    """
    undirected: Dict[str, Set[str]] = defaultdict(set)
    directed_edges: Set[Tuple[str, str]] = set()
    for r in rows:
        a = r["name_from"]
        b = r["name_to"]
        if not a or not b:
            continue
        undirected[a].add(b)
        undirected[b].add(a)
        directed_edges.add((a, b))
    return undirected, directed_edges

def connected_components(undirected: Dict[str, Set[str]]) -> List[Set[str]]:
    seen: Set[str] = set()
    comps: List[Set[str]] = []
    for node in undirected.keys():
        if node in seen:
            continue
        comp = set()
        q = deque([node])
        seen.add(node)
        while q:
            u = q.popleft()
            comp.add(u)
            for v in undirected[u]:
                if v not in seen:
                    seen.add(v)
                    q.append(v)
        comps.append(comp)
    return comps

def fmt_price_row(row: dict) -> Dict[str, str]:
    out = {}
    # On n’inclut que ce qu’on a vraiment
    for i in range(1, 6):
        key = f"price{i}"
        if key in row and row[key] != "":
            out[f"class_{i}"] = row[key]
    return out

def build_operator_structure(rows: List[dict],
                             comps: List[Set[str]],
                             directed_edges: Set[Tuple[str, str]]) -> List[dict]:
    """
    Construit la liste 'networks' :
      - network_name = 'network_1', 'network_2', ...
      - tolls = liste triée des nœuds de la composante
      - connection = dictionnaire imbriqué {origin: {dest: {...}}}
    """
    # Index par (origin_name, dest_name) -> row
    by_pair: Dict[Tuple[str, str], dict] = {}
    for r in rows:
        key = (r["name_from"], r["name_to"])
        by_pair[key] = r

    networks = []
    for idx, comp in enumerate(comps, start=1):
        # connections limitées aux paires dont les deux extrémités sont dans la composante
        connection: Dict[str, Dict[str, dict]] = defaultdict(dict)
        for (o, d), r in by_pair.items():
            if o in comp and d in comp:
                reverse_present = (d, o) in directed_edges
                connection[o][d] = {
                    "distance": r["distance"] if r.get("distance") else "",
                    "two_sides": "true" if reverse_present else "false",
                    "price": fmt_price_row(r)
                }
        network = {
            "network_name": f"network_{idx}",
            "tolls": sorted(comp),
            "connection": connection  # sera sérialisé proprement par json
        }
        networks.append(network)
    return networks

def make_payload(date_str: str,
                 version: str,
                 name: str,
                 operator_name: str,
                 currency: str,
                 networks: List[dict]) -> dict:
    payload = {
        "date": date_str,
        "version": version,
        "name": name,
        "list_of_operator": [operator_name],  # uniquement ce qu’on a
        "currency": currency,
        "operator": {
            operator_name: {
                # On ne devine pas de règle de modulation avec ces données.
                "rule": "none",
                # Pas de paramètres connus -> on n’inclut rien d’inutile.
                "networks": networks
                # "toll_geometry": {}  # non inclus : on ne l’a pas
            }
        }
    }
    return payload

def main():
    parser = argparse.ArgumentParser(
        description="Convertit des données de péage CSV (;) vers le JSON demandé, en séparant les composantes connexes."
    )
    parser.add_argument("input_csv", type=Path, help="Fichier CSV d’entrée (séparateur ;) avec en-tête.")
    parser.add_argument("output_json", type=Path, help="Fichier JSON de sortie.")
    parser.add_argument("--operator", default="AREA", help="Nom de l’opérateur à utiliser (par défaut: AREA).")
    parser.add_argument("--date", default=datetime.now().strftime("%d/%m/%Y"),
                        help="Date au format JJ/MM/AAAA (défaut: aujourd’hui).")
    parser.add_argument("--version", default="1.0", help="Version du schéma (défaut: 1.0).")
    parser.add_argument("--name", default="price_format", help="Nom du schéma (défaut: price_format).")
    parser.add_argument("--currency", default="EUR", help="Devise (défaut: EUR).")

    args = parser.parse_args()

    rows = read_semicolon_csv(args.input_csv)

    # Construire graphe et composantes
    undirected, directed_edges = build_graph(rows)
    if not undirected:
        # Si un péage est isolé (aucune arête), on l’ajoute pour qu’il forme sa propre composante
        # (cas rare car nos données sont par paires)
        isolated_nodes = set()
        for r in rows:
            isolated_nodes.add(r["name_from"])
            isolated_nodes.add(r["name_to"])
        undirected = {n: set() for n in isolated_nodes}

    comps = connected_components(undirected)

    networks = build_operator_structure(rows, comps, directed_edges)

    payload = make_payload(
        date_str=args.date,
        version=args.version,
        name=args.name,
        operator_name=args.operator,
        currency=args.currency,
        networks=networks
    )

    # Tri des clés pour lisibilité, ensure_ascii False pour les accents
    args.output_json.write_text(json.dumps(payload, indent=4, ensure_ascii=False), encoding="utf-8")
    print(f"OK → {args.output_json}")

if __name__ == "__main__":
    main()
