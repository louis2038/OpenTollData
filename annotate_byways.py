#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Annoter les connexions de péages par les 'way.id' OSM réellement traversés.

Usage:
  python annotate_byways.py price_format.json overpass.json output.json

Entrées:
- price_format.json : le premier JSON (date, version, networks, toll_description, etc.)
- overpass.json     : la réponse Overpass Turbo (nodes/ways du graphe)
Sortie:
- output.json       : copie du premier JSON enrichi par "by_ways": [ ... ] pour chaque connexion
"""

import json
import math
import sys
from collections import defaultdict
from heapq import heappush, heappop

# ----------------------------
# Utilitaires géodésiques
# ----------------------------

def haversine(lat1, lon1, lat2, lon2):
    """Distance en mètres entre (lat1,lon1) et (lat2,lon2)."""
    R = 6371000.0  # rayon terrestre moyen (m)
    phi1 = math.radians(lat1); phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlmb/2)**2
    return 2*R*math.asin(math.sqrt(a))

# ----------------------------
# Chargement Overpass -> Graphe
# ----------------------------

def build_graph_from_overpass(overpass):
    """
    Construit:
      - nodes: {node_id(int): (lat, lon)}
      - adj:   {u: list[(v, weight_m)]} (graphe non orienté, pondéré par distance)
      - edge_to_ways: {(min(u,v), max(u,v)): set(way_id)}
      - way_id_to_nodes: {way_id: [node ids]}
    """
    nodes = {}
    ways = []

    for el in overpass.get("elements", []):
        t = el.get("type")
        if t == "node":
            nid = int(el["id"])
            nodes[nid] = (float(el["lat"]), float(el["lon"]))
        elif t == "way":
            ways.append({"id": int(el["id"]), "nodes": [int(n) for n in el.get("nodes", [])]})

    adj = defaultdict(list)
    edge_to_ways = defaultdict(set)
    way_id_to_nodes = {}

    for w in ways:
        wid = w["id"]
        wnodes = w["nodes"]
        way_id_to_nodes[wid] = wnodes
        # Crée des arêtes pour chaque paire consécutive de nœuds
        for i in range(len(wnodes) - 1):
            u, v = wnodes[i], wnodes[i+1]
            if u in nodes and v in nodes:
                lat1, lon1 = nodes[u]
                lat2, lon2 = nodes[v]
                dist = haversine(lat1, lon1, lat2, lon2)
                # non orienté
                adj[u].append((v, dist))
                adj[v].append((u, dist))
                key = (u, v) if u < v else (v, u)
                edge_to_ways[key].add(wid)
    return nodes, adj, edge_to_ways, way_id_to_nodes

# ----------------------------
# Plus court chemin (Dijkstra)
# ----------------------------

def dijkstra_path(adj, nodes_coords, src, dst):
    """
    Retourne la liste ordonnée des nodes (src..dst) du plus court chemin,
    pondéré par distance (m). Si pas de chemin, renvoie None.
    """
    if src == dst:
        return [src]
    # file (distance cumulée, node, parent)
    heap = []
    heappush(heap, (0.0, src, None))
    dist = {src: 0.0}
    parent = {src: None}

    while heap:
        d, u, _ = heappop(heap)
        if u == dst:
            break
        if d > dist.get(u, float("inf")):
            continue
        for v, w in adj.get(u, []):
            nd = d + w
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                parent[v] = u
                heappush(heap, (nd, v, u))

    if dst not in parent:
        return None

    # remonter le chemin
    path = []
    cur = dst
    while cur is not None:
        path.append(cur)
        cur = parent[cur]
    path.reverse()
    return path

# ----------------------------
# Traduire un chemin de nodes -> suite de way.id
# ----------------------------

def ways_from_path(path_nodes, edge_to_ways):
    """
    À partir d'une liste de node ids du chemin, déduire une suite compacte de way.id
    en essayant de minimiser les changements de way quand c'est possible.
    """
    if not path_nodes or len(path_nodes) == 1:
        return []

    way_sequence = []
    current_way = None

    for i in range(len(path_nodes) - 1):
        u, v = path_nodes[i], path_nodes[i+1]
        key = (u, v) if u < v else (v, u)
        candidates = edge_to_ways.get(key)
        if not candidates:
            # Edge orpheline (ne devrait pas arriver si le graphe vient des ways)
            continue
        if current_way in candidates:
            # on reste sur la même way
            chosen = current_way
        else:
            # essayer d'anticiper le prochain segment pour rester sur la même way
            chosen = None
            if i + 2 < len(path_nodes):
                w_next = path_nodes[i+1]
                x_next = path_nodes[i+2]
                key_next = (w_next, x_next) if w_next < x_next else (x_next, w_next)
                next_candidates = edge_to_ways.get(key_next, set())
                inter = candidates.intersection(next_candidates)
                if inter:
                    chosen = next(iter(inter))
            if chosen is None:
                # sinon prendre un candidat au hasard (déterministe)
                chosen = sorted(candidates)[0]

        if chosen != current_way:
            way_sequence.append(chosen)
            current_way = chosen

    return way_sequence

# ----------------------------
# Récupérer le nœud OSM d’un péage
# ----------------------------

def pick_osm_node_for_toll(toll_entry, nodes):
    """
    Essaye d'abord le premier node_id déclaré dans toll_description.
    À défaut, prend le nœud OSM le plus proche des lat/lon du péage.
    Renvoie un int (node id) ou None si impossible.
    """
    # 1) Essayer node_id[0]
    node_ids = toll_entry.get("node_id") or []
    if node_ids:
        try_ids = []
        for v in node_ids:
            # certains JSON contiennent des ids en str
            try:
                try_ids.append(int(v))
            except Exception:
                pass
        for nid in try_ids:
            if nid in nodes:
                return nid

    # 2) fallback par proximité géographique
    try:
        lat = float(toll_entry["lat"])
        lon = float(toll_entry["lon"])
    except Exception:
        return None

    # Trouver le plus proche
    best = None
    best_d = float("inf")
    for nid, (nlat, nlon) in nodes.items():
        d = haversine(lat, lon, nlat, nlon)
        if d < best_d:
            best_d = d
            best = nid
    return best

# ----------------------------
# Pipeline principal
# ----------------------------

def annotate_connections_with_ways(price_data, overpass):
    nodes, adj, edge_to_ways, way_id_to_nodes = build_graph_from_overpass(overpass)

    toll_desc = price_data.get("toll_description", {})

    # Préparer un cache des nœuds OSM sélectionnés par péage
    toll_to_osmnode = {}
    for toll_name, entry in toll_desc.items():
        nid = pick_osm_node_for_toll(entry, nodes)
        if nid is not None:
            toll_to_osmnode[toll_name] = nid

    # Parcourir tous les networks / connections
    for net in price_data.get("networks", []):
        connection = net.get("connection", {})
        for src_toll, dests in connection.items():
            for dst_toll, conn_payload in dests.items():
                # trouver le nœud source et destination
                src_node = toll_to_osmnode.get(src_toll)
                dst_node = toll_to_osmnode.get(dst_toll)

                if src_node is None or dst_node is None:
                    # Impossible d'ancrer un des péages: on laisse tomber proprement
                    conn_payload["by_ways"] = []
                    conn_payload["_note"] = "OSM node not found for source or destination toll"
                    continue

                # Plus court chemin
                path_nodes = dijkstra_path(adj, nodes, src_node, dst_node)
                if not path_nodes:
                    conn_payload["by_ways"] = []
                    conn_payload["_note"] = "No path found between toll OSM nodes"
                    continue

                # Suite de way.id
                way_ids_seq = ways_from_path(path_nodes, edge_to_ways)

                # Ajout dans le JSON (ids en int)
                conn_payload["by_ways"] = way_ids_seq

    return price_data

# ----------------------------
# CLI
# ----------------------------

def main(argv):
    if len(argv) != 4:
        print("Usage: python annotate_byways.py price_format.json overpass.json output.json")
        sys.exit(1)

    price_path = argv[1]
    overpass_path = argv[2]
    output_path = argv[3]

    with open(price_path, "r", encoding="utf-8") as f:
        price_data = json.load(f)

    with open(overpass_path, "r", encoding="utf-8") as f:
        overpass = json.load(f)

    enriched = annotate_connections_with_ways(price_data, overpass)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(enriched, f, ensure_ascii=False, indent=2)

    print(f"OK ✓  Fichier enrichi écrit dans: {output_path}")

if __name__ == "__main__":
    main(sys.argv)
