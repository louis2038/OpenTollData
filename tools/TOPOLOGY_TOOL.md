# Road Topology Tool

This document describes the purpose of the experimental topology/debugging tools in `tools/`.

## Goal

The toll price database needs more than price tables and OSM coordinates. It needs a logical representation of the toll road network: which tolls belong together, where vehicles can enter, where they can exit, and which price relations make sense.

The goal is to build a manual-first tool that helps create this logical topology. Once the topology is reliable, it can be used to detect anomalies automatically.

## Why This Is Hard

OpenStreetMap contains roads, nodes, ways, and toll booths, but the toll pricing logic is not directly encoded as a clean graph.

Hard cases include:

- one physical toll station represented by several OSM nodes;
- separate north/south entry and exit logic;
- open toll barriers mixed with closed toll systems;
- operator names that do not match OSM names;
- nearby toll booths that are geographically close but logically different;
- duplicated names or aliases across operators;
- price tables that imply relations not obvious from OSM alone.

For this reason, topology creation needs manual editing and visual debugging before it can become automated.

## Current Prototype

The current prototype is:

```text
tools/map_graph_editor/index.html
```

It is a small static Leaflet editor with:

- OSM-based map backgrounds;
- node creation;
- node moving;
- node deletion;
- straight-line links between nodes;
- JSON import/export;
- node editing;
- node types such as `empty`, `toll`, `open`, and `connect`;
- connect options such as `Se`, `Sn`, `Es`, and `En`.

It is intentionally simple. The objective is to build an inspectable graph, not a complete GIS application.

## CSV Import

The helper script:

```text
tools/map_graph_editor/import_toll_info.py
```

converts `GLOBAL_toll_info.csv` into the graph JSON format used by the editor.

Example:

```bash
python tools/map_graph_editor/import_toll_info.py \
  tools/map_graph_editor/GLOBAL_toll_info.csv \
  --json tools/map_graph_editor/graph.json
```

The import is conservative:

- existing nodes are matched by `toll_name`;
- existing manual types are preserved;
- existing links are preserved;
- positions are preserved unless `--refresh-position` is used;
- `open` tolls can be inferred from the CSV without turning edited nodes back into `empty`.

## Node Model

Current node fields:

```json
{
  "id": "n1",
  "type": "empty",
  "name": "",
  "toll_name": "CONDRIEU",
  "nbs_booth": "2",
  "connectOptions": [],
  "attrs": {},
  "lat": 45.5055132,
  "lng": 4.8406636
}
```

Important fields:

- `type`: visual/logical node type.
- `toll_name`: stable identifier from `GLOBAL_toll_info.csv`.
- `nbs_booth`: number of OSM toll booth nodes from the CSV.
- `connectOptions`: direction/function flags for connect nodes.
- `attrs`: free JSON object for debug information.

## Connect Options

Connect nodes can represent directional entry/exit logic.

Current flags:

```text
Se = entrée sud
Sn = entrée nord
Es = sortie sud
En = sortie nord
```

These names may evolve once the topology model becomes more formal.

## Future Uses

Once enough topology has been manually created, the graph can be used to:

- detect missing price relations;
- detect impossible entry/exit combinations;
- detect isolated or suspicious toll nodes;
- compare operator price tables against expected topology;
- highlight name conflicts and duplicated physical tolls;
- improve automatic validation before JSON export.

## Design Principle

The tool should not silently overwrite manual work. Imports and refreshes must preserve user-edited node types, links, and attributes unless an explicit option says otherwise.
