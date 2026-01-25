#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convertit un JSON Overpass (péages) en CSV agrégé par nom de péage.

Colonnes :
- osm_name : nom du péage (tags.name)
- operator_ref : valeur de tags["operator:ref"] si dispo, sinon tags["operator_ref"], sinon tags["operator"]
- lat, lon : barycentre (moyenne) des cabines (nodes) de même nom
- nbs_booth : nombre de cabines (nodes) pour ce nom
- booth_node_id : liste JSON des ids OSM des cabines associées

Important :
- Dans OSM, les cabines de péage sont le plus souvent taguées **barrier=toll_booth** (et non highway=toll_booth).
- Assure-toi que ta requête Overpass renvoie bien les tags (ex: `out body;`). Si tu utilises `out skel;`, les nodes n'auront pas leurs tags.

Usage :
    python overpass_peages_to_csv.py input.json -o output.csv
"""

import argparse
import csv
import json
from collections import defaultdict

TOLL_KEYS = ("barrier", "highway", "amenity")
TOLL_VALUES = {"toll_booth"}  # on tolère plusieurs clés possibles


def extract_operator_ref(tags: dict) -> str:
    if not tags:
        return ""
    return (
        tags.get("operator:ref")
        or tags.get("operator_ref")
        or tags.get("operator")
        or ""
    )


def is_toll_booth_node(el: dict) -> bool:
    if el.get("type") != "node":
        return False
    tags = el.get("tags") or {}
    if not isinstance(tags, dict):
        return False
    # La norme OSM est barrier=toll_booth ; on accepte aussi highway/amenity par tolérance
    for k in TOLL_KEYS:
        v = tags.get(k)
        if v in TOLL_VALUES:
            return True
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Convertit un export Overpass JSON (toll_booth) en CSV agrégé par nom."
    )
    parser.add_argument(
        "input_json", help="Chemin du fichier .json (résultat Overpass Turbo)"
    )
    parser.add_argument(
        "-o",
        "--output_csv",
        default="peages.csv",
        help="Chemin du CSV de sortie (défaut: peages.csv)",
    )
    args = parser.parse_args()

    with open(args.input_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    elements = data.get("elements", [])
    # Filtrer uniquement les nodes représentant des cabines de péage
    booths = []
    for el in elements:
        if not is_toll_booth_node(el):
            continue
        tags = el.get("tags") or {}
        name = tags.get("name") or "UNKNOWN"
        booths.append(
            {
                "id": el.get("id"),
                "name": name,
                "lat": el.get("lat"),
                "lon": el.get("lon"),
                "operator_ref": extract_operator_ref(tags),
            }
        )

    # Agrégation par nom
    grouped = defaultdict(list)
    for b in booths:
        grouped[b["name"]].append(b)

    # Construire les lignes de sortie
    rows = []
    for name, items in grouped.items():
        coords = [
            (i.get("lat"), i.get("lon"))
            for i in items
            if isinstance(i.get("lat"), (int, float))
            and isinstance(i.get("lon"), (int, float))
        ]
        if coords:
            lat = sum(lat for lat, _ in coords) / len(coords)
            lon = sum(lon for _, lon in coords) / len(coords)
        else:
            lat = lon = float("nan")
        n = len(items)
        ids = [i["id"] for i in items if i.get("id") is not None]
        # Choisir un operator_ref : si tous identiques, garder la valeur commune, sinon vide
        op_values = {i["operator_ref"] for i in items if i.get("operator_ref")}
        operator_ref = list(op_values)[0] if len(op_values) == 1 else ""

        rows.append(
            {
                "osm_name": name,
                "operator_ref": operator_ref,
                "lat": f"{lat:.7f}" if isinstance(lat, float) else "",
                "lon": f"{lon:.7f}" if isinstance(lon, float) else "",
                "nbs_booth": n,
                "booth_node_id": json.dumps(ids, ensure_ascii=False),
            }
        )

    # Écriture CSV
    fieldnames = [
        "osm_name",
        "operator_ref",
        "lat",
        "lon",
        "nbs_booth",
        "booth_node_id",
    ]
    with open(args.output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    # Messages d'aide si rien trouvé
    if not rows:
        print("⚠️ Aucun node de péage trouvé dans ce JSON.")
        print(
            "Vérifie que tes cabines sont bien taguées barrier=toll_booth (ou highway/amenity=toll_booth)"
        )
        print("et que la requête Overpass inclut les tags (utilise `out body;`).")

    print(f"✅ {len(rows)} ligne(s) écrite(s) dans {args.output_csv}")


if __name__ == "__main__":
    main()
