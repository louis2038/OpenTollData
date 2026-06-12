#!/usr/bin/env python3
"""Import GLOBAL_toll_info.csv into the map graph editor JSON format."""

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"nodes": [], "edges": []}

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Invalid JSON root in {path}: expected object")

    data.setdefault("nodes", [])
    data.setdefault("edges", [])
    if not isinstance(data["nodes"], list) or not isinstance(data["edges"], list):
        raise ValueError(f"Invalid graph JSON in {path}: nodes/edges must be arrays")

    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def next_node_number(nodes: list[dict[str, Any]]) -> int:
    numbers = []
    for node in nodes:
        node_id = str(node.get("id", ""))
        if node_id.startswith("n") and node_id[1:].isdigit():
            numbers.append(int(node_id[1:]))
    return max(numbers, default=0) + 1


def csv_attrs(row: dict[str, str]) -> dict[str, str]:
    return {
        "osm_name": row.get("osm_name", ""),
        "operator_ref": row.get("operator_ref", ""),
        "booth_node_id": row.get("booth_node_id", ""),
        "booth_way_id": row.get("booth_way_id", ""),
        "toll_info_type": row.get("type", ""),
        "operator_osm": row.get("operator_osm", ""),
    }


def graph_type_from_toll_info(row: dict[str, str]) -> str:
    """Convertit le type toll_info CSV vers un type de noeud de l'éditeur."""
    return "open" if (row.get("type") or "").strip().lower() == "open" else "empty"


def normalize_existing_node(node: dict[str, Any]) -> None:
    node.setdefault("type", "empty")
    node.setdefault("name", "")
    node.setdefault("toll_name", "")
    node.setdefault("nbs_booth", "")
    node.setdefault("connectOptions", [])
    node.setdefault("attrs", {})

    if not isinstance(node["connectOptions"], list):
        node["connectOptions"] = []
    if not isinstance(node["attrs"], dict):
        node["attrs"] = {}


def merge_csv_into_graph(
    csv_path: Path,
    graph: dict[str, Any],
    refresh_position: bool,
    refresh_type: bool,
) -> tuple[int, int]:
    nodes = graph["nodes"]
    for node in nodes:
        if isinstance(node, dict):
            normalize_existing_node(node)

    nodes_by_toll_name = {
        str(node.get("toll_name", "")): node
        for node in nodes
        if isinstance(node, dict) and node.get("toll_name")
    }

    created = 0
    updated = 0
    node_number = next_node_number(nodes)

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            toll_name = (row.get("name") or "").strip()
            if not toll_name:
                continue

            lat_raw = (row.get("lat") or "").strip()
            lon_raw = (row.get("lon") or "").strip()
            if not lat_raw or not lon_raw:
                continue

            try:
                lat = float(lat_raw)
                lng = float(lon_raw)
            except ValueError:
                continue

            node = nodes_by_toll_name.get(toll_name)
            if node is None:
                node = {
                    "id": f"n{node_number}",
                    "type": graph_type_from_toll_info(row),
                    "name": "",
                    "toll_name": toll_name,
                    "nbs_booth": (row.get("nbs_booth") or "").strip(),
                    "connectOptions": [],
                    "attrs": csv_attrs(row),
                    "lat": lat,
                    "lng": lng,
                }
                node_number += 1
                nodes.append(node)
                nodes_by_toll_name[toll_name] = node
                created += 1
                continue

            normalize_existing_node(node)
            node["toll_name"] = toll_name
            node["nbs_booth"] = (row.get("nbs_booth") or "").strip()
            if refresh_type:
                csv_node_type = graph_type_from_toll_info(row)
                if csv_node_type != "empty" or node.get("type") == "empty":
                    node["type"] = csv_node_type
                    if node["type"] != "connect":
                        node["connectOptions"] = []
            if refresh_position:
                node["lat"] = lat
                node["lng"] = lng
            else:
                node.setdefault("lat", lat)
                node.setdefault("lng", lng)

            node["attrs"].update(csv_attrs(row))
            updated += 1

    return created, updated


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convertit GLOBAL_toll_info.csv vers le JSON de tools/map_graph_editor."
    )
    parser.add_argument("csv", type=Path, help="Fichier GLOBAL_toll_info.csv")
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        help="JSON existant à actualiser. Défaut: graph.json à côté du CSV.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Fichier JSON de sortie. Défaut: valeur de --json.",
    )
    parser.add_argument(
        "--refresh-position",
        action="store_true",
        help="Force la mise à jour lat/lng depuis le CSV pour les noeuds existants.",
    )
    parser.add_argument(
        "--refresh-type",
        action="store_true",
        help=(
            "Actualise le type depuis le CSV pour les noeuds existants, sans jamais "
            "remplacer un type édité par 'empty'."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    csv_path = args.csv
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)

    json_path = args.json or csv_path.with_name("graph.json")
    out_path = args.out or json_path

    graph = read_json(json_path)
    created, updated = merge_csv_into_graph(
        csv_path,
        graph,
        refresh_position=args.refresh_position,
        refresh_type=args.refresh_type,
    )
    write_json(out_path, graph)

    print(f"OK -> {out_path}")
    print(f"Noeuds créés: {created}")
    print(f"Noeuds actualisés: {updated}")
    print(f"Noeuds total: {len(graph['nodes'])}")
    print(f"Arêtes conservées: {len(graph['edges'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
