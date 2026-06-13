#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2025-2026 Louis TRIOULEYRE-ROBERJOT
# This file is part of TollData - Open French Highway Toll Database

"""
overpass2geojson_nodes_ways.py
Convertit un JSON Overpass en GeoJSON en reconstruisant les ways via leurs nodes si 'geometry' est absent.

Usage:
  python overpass2geojson_nodes_ways.py input.json output.geojson
"""

import json
import sys
from typing import Dict, Any, List, Tuple


def build_properties(el: Dict[str, Any]) -> Dict[str, Any]:
    props = {"@id": el.get("id"), "@type": el.get("type")}
    tags = el.get("tags", {})
    if isinstance(tags, dict):
        props.update(tags)
    return props


def node_to_point(el: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [el["lon"], el["lat"]]},
        "properties": build_properties(el),
    }


def is_closed_coords(coords: List[List[float]]) -> bool:
    if len(coords) < 4:
        return False
    return coords[0][0] == coords[-1][0] and coords[0][1] == coords[-1][1]


def geometry_to_feature(el: Dict[str, Any]) -> Dict[str, Any]:
    coords = [[pt["lon"], pt["lat"]] for pt in el["geometry"]]
    if is_closed_coords(coords):
        geom = {"type": "Polygon", "coordinates": [coords]}
    else:
        geom = {"type": "LineString", "coordinates": coords}
    return {"type": "Feature", "geometry": geom, "properties": build_properties(el)}


def rebuild_way_from_nodes(el: Dict[str, Any], node_index: Dict[int, Tuple[float, float]]) -> Tuple[Dict[str, Any], int]:
    """
    Tente de reconstruire un way à partir de sa liste de nodes.
    Retourne (feature, missing_count). Si des nodes manquent, feature = None.
    """
    node_ids = el.get("nodes", [])
    coords: List[List[float]] = []
    missing = 0
    for nid in node_ids:
        xy = node_index.get(nid)
        if xy is None:
            missing += 1
            # on continue pour compter tous les manquants
        else:
            coords.append([xy[0], xy[1]])

    if missing > 0 or len(coords) < 2:
        return None, missing

    # Si premier et dernier node id identiques, ferme l’anneau (souvent déjà le cas)
    if node_ids and node_ids[0] == node_ids[-1]:
        if not is_closed_coords(coords):
            coords.append(coords[0])  # garantir la fermeture

    if is_closed_coords(coords):
        geom = {"type": "Polygon", "coordinates": [coords]}
    else:
        geom = {"type": "LineString", "coordinates": coords}

    feature = {"type": "Feature", "geometry": geom, "properties": build_properties(el)}
    return feature, 0


def overpass_to_geojson(overpass: Dict[str, Any]) -> Dict[str, Any]:
    elements = overpass.get("elements", [])
    features: List[Dict[str, Any]] = []

    # 1) Index des nodes
    node_index: Dict[int, Tuple[float, float]] = {}
    for el in elements:
        if el.get("type") == "node" and "lat" in el and "lon" in el:
            node_index[int(el["id"])] = (float(el["lon"]), float(el["lat"]))

    ignored_no_geom = 0
    rebuilt = 0
    missing_nodes_total = 0

    # 2) Conversion
    for el in elements:
        el_type = el.get("type")

        if el_type == "node" and "lat" in el and "lon" in el:
            try:
                features.append(node_to_point(el))
            except Exception as e:
                print(f"[WARN] Node {el.get('id')} ignoré (erreur: {e})", file=sys.stderr)

        elif "geometry" in el and isinstance(el["geometry"], list) and el["geometry"]:
            try:
                features.append(geometry_to_feature(el))
            except Exception as e:
                print(f"[WARN] Élément {el_type} {el.get('id')} ignoré (erreur: {e})", file=sys.stderr)

        elif el_type == "way" and isinstance(el.get("nodes"), list) and el["nodes"]:
            feature, missing = rebuild_way_from_nodes(el, node_index)
            if feature is not None:
                features.append(feature)
                rebuilt += 1
            else:
                ignored_no_geom += 1
                missing_nodes_total += missing
        else:
            ignored_no_geom += 1

    if ignored_no_geom:
        msg = f"[INFO] {ignored_no_geom} élément(s) sans géométrie exploitable ignoré(s)"
        if missing_nodes_total:
            msg += f" (dont {missing_nodes_total} référence(s) de node introuvable(s))"
        msg += "."
        print(msg, file=sys.stderr)

    print(f"[INFO] Ways reconstruits via nodes: {rebuilt}", file=sys.stderr)

    return {"type": "FeatureCollection", "features": features}


def main():
    if len(sys.argv) != 3:
        print("Usage: python overpass2geojson_nodes_ways.py input.json output.geojson", file=sys.stderr)
        sys.exit(1)

    input_path, output_path = sys.argv[1], sys.argv[2]

    with open(input_path, "r", encoding="utf-8") as f:
        overpass = json.load(f)

    geojson = overpass_to_geojson(overpass)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

    print(f"[OK] Écrit: {output_path} ({len(geojson['features'])} features)", file=sys.stderr)


if __name__ == "__main__":
    main()
