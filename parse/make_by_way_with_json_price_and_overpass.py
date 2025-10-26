#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build "by_way" lists for each connection in a price_format JSON
AND build a top-level "by_way" summary block with per-way length,
average prices per class, and list of relations that use each way.

Usage:
  python build_by_way_from_overpass.py --price price_format.json --overpass overpass.json --out output.json
  python build_by_way_from_overpass.py --price price_format.json --overpass overpass.json --csv output.csv

Average price formula per way (for each class):
  average_price = mean_over_relations( used_length_of_way_in_relation_km * ( relation_price_class / relation_total_distance_km ) )

Notes:
- The graph is directed and respects OSM oneway semantics to avoid "contre-sens".
- For each connection (e.g., AITON -> CHIGNIN BARRIERE), we try progressively more source toll nodes
  in the given order, and keep the globally shortest path if reachable.
- The "by_way" in each connection contains all OSM way IDs along that path (unique, in path order).
- The top-level "by_way" block aggregates across all connections.
"""

import json
import math
import csv
import argparse
from collections import defaultdict, OrderedDict
import heapq
from typing import Dict, List, Tuple, Any, Optional, Set


# --------------------------- Geo helpers ---------------------------

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Returns distance in meters between two WGS84 points.
    """
    R = 6371000.0  # meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# --------------------------- Graph building ---------------------------

class DirectedGraph:
    def __init__(self):
        # adjacency: u -> list of (v, weight_m, way_id)
        self.adj: Dict[int, List[Tuple[int, float, int]]] = defaultdict(list)
        # node coordinates: node_id -> (lat, lon)
        self.coords: Dict[int, Tuple[float, float]] = {}
        # For mapping consecutive node pairs to way_ids (could be multiple ways)
        self.edge_to_wayids: Dict[Tuple[int, int], List[int]] = defaultdict(list)

    def add_node(self, nid: int, lat: float, lon: float):
        self.coords[nid] = (lat, lon)

    def add_edge(self, u: int, v: int, way_id: int):
        if u not in self.coords or v not in self.coords:
            return
        lat1, lon1 = self.coords[u]
        lat2, lon2 = self.coords[v]
        w = haversine_m(lat1, lon1, lat2, lon2)
        self.adj[u].append((v, w, way_id))
        self.edge_to_wayids[(u, v)].append(way_id)


def is_oneway_forward(tags: Dict[str, str], highway: Optional[str]) -> Optional[bool]:
    """
    Determine oneway direction:
    - Return True for forward only
    - Return False for reverse only
    - Return None for bidirectional

    OSM rules approximated:
    - highway=motorway or motorway_link is oneway by default unless oneway=no
    - Consider oneway values: yes/1/true/forward  => forward
                             -1/reverse           => reverse
                             no/0/false           => bidirectional
    """
    oneway = None
    if tags is None:
        tags = {}

    val = (tags.get("oneway") or "").strip().lower()
    if val in {"yes", "1", "true", "forward"}:
        oneway = True
    elif val in {"-1", "reverse"}:
        oneway = False
    elif val in {"no", "0", "false"}:
        oneway = None

    # default oneway for motorways
    if oneway is None and highway in {"motorway", "motorway_link"}:
        # unless explicitly set to "no"
        if val not in {"no", "0", "false"}:
            oneway = True

    return oneway


def build_directed_graph_and_way_lengths(overpass: Dict[str, Any]):
    """
    Build a directed graph from Overpass JSON and compute total length per way.
    Returns:
      G: DirectedGraph
      way_id_to_nodes: Dict[int, List[int]]
      way_total_len_km: Dict[int, float]
    """
    G = DirectedGraph()
    nodes: Dict[int, Tuple[float, float]] = {}
    ways: Dict[int, Dict[str, Any]] = {}

    for el in overpass.get("elements", []):
        typ = el.get("type")
        if typ == "node":
            nid = int(el["id"])
            lat = float(el["lat"])
            lon = float(el["lon"])
            nodes[nid] = (lat, lon)
        elif typ == "way":
            wid = int(el["id"])
            ways[wid] = {
                "id": wid,
                "nodes": [int(n) for n in el.get("nodes", [])],
                "tags": el.get("tags", {}) or {},
            }

    # add nodes
    for nid, (lat, lon) in nodes.items():
        G.add_node(nid, lat, lon)

    # helper to length of a way
    def way_len_km(nlist: List[int]) -> float:
        d = 0.0
        for u, v in zip(nlist, nlist[1:]):
            if u in nodes and v in nodes:
                (lat1, lon1) = nodes[u]
                (lat2, lon2) = nodes[v]
                d += haversine_m(lat1, lon1, lat2, lon2)
        return d / 1000.0

    # add directed edges and compute lengths
    way_id_to_nodes: Dict[int, List[int]] = {}
    way_total_len_km: Dict[int, float] = {}

    for wid, wdata in ways.items():
        nlist: List[int] = wdata["nodes"]
        tags: Dict[str, str] = wdata["tags"]
        highway = (tags.get("highway") or "").lower() if tags else ""
        oneway = is_oneway_forward(tags, highway)

        # store
        way_id_to_nodes[wid] = nlist
        way_total_len_km[wid] = way_len_km(nlist)

        # edges in forward direction
        for u, v in zip(nlist, nlist[1:]):
            if oneway is None:
                # bidirectional: add both directions
                G.add_edge(u, v, wid)
                G.add_edge(v, u, wid)
            elif oneway is True:
                # forward only
                G.add_edge(u, v, wid)
            elif oneway is False:
                # reverse only
                G.add_edge(v, u, wid)

    return G, way_id_to_nodes, way_total_len_km


# --------------------------- Shortest path (Dijkstra) ---------------------------

def dijkstra_shortest_path(
    G: DirectedGraph,
    sources: List[int],
    targets: Set[int]
) -> Tuple[float, List[int]]:
    """
    Multi-source Dijkstra from any of 'sources' to any node in 'targets'.
    Returns (distance_m, path_node_ids). If no path, returns (inf, []).
    """
    dist: Dict[int, float] = {}
    prev: Dict[int, Optional[int]] = {}
    pq: List[Tuple[float, int]] = []

    for s in sources:
        if s in G.coords:
            dist[s] = 0.0
            prev[s] = None
            heapq.heappush(pq, (0.0, s))

    best_target: Optional[int] = None

    while pq:
        d, u = heapq.heappop(pq)
        if d > dist.get(u, float("inf")):
            continue
        if u in targets:
            best_target = u
            break
        for v, w, _way in G.adj.get(u, []):
            nd = d + w
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))

    if best_target is None:
        return float("inf"), []

    # Reconstruct path
    path: List[int] = []
    cur = best_target
    while cur is not None:
        path.append(cur)
        cur = prev.get(cur)
    path.reverse()
    return dist[best_target], path


# --------------------------- Path helpers ---------------------------

def build_pair_to_way_index(way_id_to_nodes: Dict[int, List[int]]) -> Dict[Tuple[int, int], List[int]]:
    """
    Build an index mapping (u,v) node pair -> list of way_ids that contain that directed pair.
    """
    idx: Dict[Tuple[int, int], List[int]] = defaultdict(list)
    for wid, nlist in way_id_to_nodes.items():
        for u, v in zip(nlist, nlist[1:]):
            idx[(u, v)].append(wid)
    return idx


def path_nodes_to_steps(
    G: DirectedGraph,
    path_nodes: List[int],
    pair_to_wayids: Dict[Tuple[int, int], List[int]]
) -> List[Tuple[int, int, int, float]]:
    """
    Convert a path [n0, n1, ..., nk] to a list of steps with way IDs and segment lengths:
      returns list of (u, v, way_id, seg_len_km)
    We choose the first available way_id that maps (u,v).
    """
    steps: List[Tuple[int, int, int, float]] = []
    for u, v in zip(path_nodes, path_nodes[1:]):
        wayids = pair_to_wayids.get((u, v), [])
        if not wayids:
            # fallback: inspect adjacency to find any matching edge, and take its way_id
            cand = None
            for vv, w_m, wid in G.adj.get(u, []):
                if vv == v:
                    cand = wid
                    break
            if cand is None:
                continue
            wid = cand
        else:
            wid = wayids[0]

        (lat1, lon1) = G.coords[u]
        (lat2, lon2) = G.coords[v]
        seg_len_km = haversine_m(lat1, lon1, lat2, lon2) / 1000.0
        steps.append((u, v, wid, seg_len_km))
    return steps


def unique_way_order(steps: List[Tuple[int, int, int, float]]) -> List[int]:
    seen = set()
    ordered: List[int] = []
    for _, _, wid, _ in steps:
        if wid not in seen:
            seen.add(wid)
            ordered.append(wid)
    return ordered


# --------------------------- Main processing ---------------------------

def compute_by_way_for_price_format(price_data: Dict[str, Any], overpass: Dict[str, Any]) -> Dict[str, Any]:
    G, way_id_to_nodes, way_total_len_km = build_directed_graph_and_way_lengths(overpass)
    pair_to_wayids = build_pair_to_way_index(way_id_to_nodes)

    toll_desc_key = "toll_description"
    if toll_desc_key not in price_data:
        raise KeyError(f'"{toll_desc_key}" not found in price JSON')

    toll_desc: Dict[str, Any] = price_data[toll_desc_key]

    def name_to_node_list(toll_name: str) -> List[int]:
        td = toll_desc.get(toll_name)
        if not td:
            return []
        return [int(x) for x in td.get("node_id", [])]

    # --- Accumulators for top-level by_way ---
    # For each way: relations encountered (preserve insertion order), sum contributions per class, count relations
    relations_by_way: Dict[int, List[Tuple[str, str]]] = defaultdict(list)
    relations_seen_by_way: Dict[int, Set[Tuple[str, str]]] = defaultdict(set)
    sum_contrib_by_way_class: Dict[int, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    count_rel_by_way: Dict[int, int] = defaultdict(int)

    # Iterate networks -> connection -> source -> dest
    for comp in price_data.get("networks", []):
        conn = comp.get("connection", {})
        for src_name, dests in conn.items():
            src_nodes_ordered = name_to_node_list(src_name)

            for dest_name, payload in dests.items():
                dest_nodes_ordered = name_to_node_list(dest_name)
                dest_nodes_set = set(dest_nodes_ordered)

                best_dist = float("inf")
                best_path: List[int] = []

                # progressively include more sources (1st, then 1st+2nd, ...)
                cumulative_sources: List[int] = []
                for s in src_nodes_ordered:
                    cumulative_sources.append(int(s))
                    d, path = dijkstra_shortest_path(G, cumulative_sources, dest_nodes_set)
                    if path and d < best_dist:
                        best_dist = d
                        best_path = path

                if not best_path:
                    payload["by_way"] = []
                    continue

                # Steps with way IDs and lengths
                steps = path_nodes_to_steps(G, best_path, pair_to_wayids)
                way_ids_in_order = unique_way_order(steps)
                payload["by_way"] = [str(w) for w in way_ids_in_order]

                # Per-connection used length per way
                used_len_km_by_way: Dict[int, float] = defaultdict(float)
                for _, _, wid, seglen in steps:
                    used_len_km_by_way[wid] += seglen

                # Connection total distance (km) from the input JSON
                try:
                    total_km = float(payload.get("distance", "0").replace(",", "."))
                except Exception:
                    total_km = 0.0

                if total_km <= 0:
                    # Can't allocate proportionally without a positive distance
                    continue

                # Price per class for this connection
                price_map = payload.get("price", {})
                # Mark which ways appear in this relation (to increment counts once per relation)
                ways_in_relation = list(used_len_km_by_way.keys())

                # For each way in this relation, compute contribution and accumulate
                for wid in ways_in_relation:
                    # register relation
                    rel_pair = (src_name, dest_name)
                    if rel_pair not in relations_seen_by_way[wid]:
                        relations_seen_by_way[wid].add(rel_pair)
                        relations_by_way[wid].append(rel_pair)
                        count_rel_by_way[wid] += 1

                    used_km = used_len_km_by_way[wid]

                    for cls, price_str in price_map.items():
                        try:
                            price_val = float(str(price_str).replace(",", "."))
                        except Exception:
                            continue
                        contrib = used_km * (price_val / total_km)
                        sum_contrib_by_way_class[wid][cls] += contrib

    # Build the top-level by_way block
    top_by_way: Dict[str, Any] = {}
    for wid_int, rel_list in relations_by_way.items():
        rel_count = count_rel_by_way.get(wid_int, 0)
        if rel_count == 0:
            continue

        # average per class
        avg_price: Dict[str, str] = {}
        for cls, s in sum_contrib_by_way_class[wid_int].items():
            avg = s / rel_count
            avg_price[cls] = f"{avg:.3g}"

        # way length (total OSM length)
        wlen = way_total_len_km.get(wid_int, 0.0)
        top_by_way[str(wid_int)] = {
            "length": f"{wlen:.3f}",
            "average_price": avg_price,
            "relation": [{"from": a, "to": b} for (a, b) in rel_list],
        }

    price_data["by_way"] = top_by_way
    return price_data


# --------------------------- CSV Export ---------------------------

def export_connections_to_csv(price_data: Dict[str, Any], overpass: Dict[str, Any], output_path: str):
    """
    Build directed graph and export all connections to CSV.
    CSV format: name_from;name_to;by_way;distance;class_1;...;class_5
    where by_way contains comma-separated OSM way IDs.
    """
    G, way_id_to_nodes, _ = build_directed_graph_and_way_lengths(overpass)
    pair_to_wayids = build_pair_to_way_index(way_id_to_nodes)
    
    toll_desc = price_data.get("toll_description", {})
    
    def name_to_node_list(toll_name: str) -> List[int]:
        td = toll_desc.get(toll_name)
        if not td:
            return []
        return [int(x) for x in td.get("node_id", [])]
    
    # Prepare CSV rows
    rows = []
    
    # Get all price classes from first connection found
    price_classes = []
    for comp in price_data.get("networks", []):
        conn = comp.get("connection", {})
        for src_name, dests in conn.items():
            for dest_name, payload in dests.items():
                price_map = payload.get("price", {})
                price_classes = sorted(price_map.keys())
                break
            if price_classes:
                break
        if price_classes:
            break
    
    # Process all connections
    for comp in price_data.get("networks", []):
        conn = comp.get("connection", {})
        for src_name, dests in conn.items():
            src_nodes_ordered = name_to_node_list(src_name)
            
            for dest_name, payload in dests.items():
                dest_nodes_ordered = name_to_node_list(dest_name)
                dest_nodes_set = set(dest_nodes_ordered)
                
                best_dist = float("inf")
                best_path: List[int] = []
                
                # Progressively include more sources
                cumulative_sources: List[int] = []
                for s in src_nodes_ordered:
                    cumulative_sources.append(int(s))
                    d, path = dijkstra_shortest_path(G, cumulative_sources, dest_nodes_set)
                    if path and d < best_dist:
                        best_dist = d
                        best_path = path
                
                # Build by_way list
                by_way_str = ""
                if best_path:
                    steps = path_nodes_to_steps(G, best_path, pair_to_wayids)
                    way_ids_in_order = unique_way_order(steps)
                    by_way_str = ",".join(str(w) for w in way_ids_in_order)
                
                # Get distance and prices
                distance = payload.get("distance", "")
                price_map = payload.get("price", {})
                
                # Build row
                row = {
                    "name_from": src_name,
                    "name_to": dest_name,
                    "by_way": by_way_str,
                    "distance": distance
                }
                
                # Add price columns
                for cls in price_classes:
                    price_val = price_map.get(cls, "")
                    row[cls] = price_val
                
                rows.append(row)
    
    # Write CSV
    if not rows:
        print("No connections found to export")
        return
    
    fieldnames = ["name_from", "name_to", "by_way", "distance"] + price_classes
    
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"Exported {len(rows)} connections to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Add per-connection by_way lists and a global by_way summary to price_format JSON using Overpass directed shortest paths, or export to CSV.")
    parser.add_argument("--price", required=True, help="Path to price_format JSON")
    parser.add_argument("--overpass", required=True, help="Path to Overpass Turbo JSON")
    parser.add_argument("--out", help="Output JSON path (for JSON mode)")
    parser.add_argument("--csv", help="Output CSV path (for CSV mode)")
    args = parser.parse_args()

    if not args.out and not args.csv:
        parser.error("Either --out (JSON) or --csv must be specified")

    with open(args.price, "r", encoding="utf-8") as f:
        price_data = json.load(f)
    with open(args.overpass, "r", encoding="utf-8") as f:
        overpass = json.load(f)

    if args.csv:
        # CSV export mode
        export_connections_to_csv(price_data, overpass, args.csv)
    else:
        # JSON enrichment mode
        enriched = compute_by_way_for_price_format(price_data, overpass)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(enriched, f, ensure_ascii=False, indent=4)
        print(f"Wrote output to {args.out}")


if __name__ == "__main__":
    main()
