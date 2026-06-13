# TollData - Open French Highway Toll Database

TollData is an open data project for French highway toll prices. The goal is to transform operator price documents into structured, reusable data that can be used by route planners, map applications, research tools, and future public services.

The project focuses first on France, but the method is meant to be reusable for other countries once the French pipeline is reliable enough.

## Why This Project Exists

Highway toll prices are public, but they are not easy to use in practice. Operators often publish tariffs as PDF tables, with different layouts, naming conventions, and edge cases. A useful database must do more than extract prices: it must also identify the physical toll booths, connect them to OpenStreetMap objects, and detect inconsistencies between operators.

The hard part is not only parsing files. The hard part is building trust in the data.

Typical difficulties include:

- PDFs are not standardized across operators.
- One operator may split data by page, area, class, or toll system.
- The same physical station can have different names depending on the operator or source.
- Some tolls are closed-system stations, while others are open-system flat-fee barriers.
- OpenStreetMap names and operator names often differ.
- Some OSM toll booths are represented by several nodes or ways.
- Automated matching can suggest wrong correspondences and must be reviewed.

## Data Produced

The pipeline produces three main CSV datasets and a final JSON network.

Closed toll prices:

```text
name_from;name_to;distance;price1;price2;price3;price4;price5
```

Open toll prices:

```text
name;distance;price1;price2;price3;price4;price5
```

Toll metadata:

```text
name;osm_name;operator_ref;lat;lon;nbs_booth;booth_node_id;booth_way_id;type;operator_osm
```

The generated JSON combines prices, toll descriptions, OSM identifiers, operators, and connected components of the closed toll network.

## Current Pipeline

The automation is organized around one directory per operator. Each operator has its own parser because the source documents are different. All parsers must eventually produce the same common CSV format.

Simplified pipeline:

```text
operator PDF / raw text
  -> operator-specific parser
  -> operator price CSVs
  -> OSM matching and enrichment
  -> manual review of toll_info
  -> global price merge
  -> validation
  -> JSON generation
```

Main operator directories:

```text
parse/ASF/
parse/APRR/
parse/AREA/
parse/COFIROUTE/
```

Each directory can contain raw data, mapping files, parser scripts, intermediate CSVs, and final operator CSVs.

## Name Conflicts And Manual Resolution

The central data quality issue is station identity. Two datasets can refer to the same physical toll station with different names, or two different stations can have names that look very similar.

Examples of problems the pipeline must handle:

- Different operator names for the same station.
- OSM names that differ from commercial/operator names.
- Aliases created by old names, barriers, directions, or page-specific labels.
- Duplicate OSM IDs shared by several operator rows.
- Stations that are close geographically but are not the same logical toll.

For this reason, `toll_info` is treated as curated data. Scripts should not overwrite it by default. Automatic generation is useful for bootstrapping, but final corrections must remain stable and reviewable.

The global merge script follows this principle: by default, `meta_global.py` merges prices and keeps the existing `GLOBAL_toll_info.csv`. Regenerating toll metadata requires an explicit option.

## Validation Philosophy

Validation is part of the pipeline, not an afterthought. The current validation scripts check that:

- every price station exists in `toll_info`;
- station types match their price file (`open` or `close`);
- numeric values are valid;
- OSM node IDs are not reused incorrectly;
- the generated JSON is structurally coherent.

Some errors cannot be solved automatically. The project therefore needs tools that make manual investigation faster and safer.

## Next Step: Logical Road Topology

The next major step is to build a tool for creating and editing the logical topology of the highway toll network.

The idea is to model the network with explicit nodes and links:

- toll nodes;
- open toll nodes;
- connection nodes;
- north/south entry and exit options;
- straight logical links between nodes;
- custom attributes for debugging.

This topology is difficult because the logical toll network is not exactly the same thing as the raw OSM road graph. However, once created, it should allow stronger automatic checks:

- detect impossible or missing price relations;
- detect suspicious isolated tolls;
- detect duplicated or inconsistent station identities;
- compare tariff relations with the expected road topology;
- improve confidence in the global database.

A first experimental editor lives in:

```text
tools/map_graph_editor/
```

See `tools/TOPOLOGY_TOOL.md` for the design notes.

## Repository Layout

```text
parse/                  Data processing pipeline and operator parsers
parse/WORKFLOW.md       Short operational workflow
tools/                  Experimental helper tools
tools/map_graph_editor/ Manual graph/topology editor prototype
LICENSE                 Code license
LICENSE-DATA            Data license
NOTICE.md               Attribution and license details
```

## Useful Commands

Global price merge while keeping curated toll metadata:

```bash
cd parse
python meta_global.py
```

Force regeneration of global toll metadata from operator files:

```bash
cd parse
python meta_global.py --forceinfo
```

Validate the global CSV triplet:

```bash
cd parse
python validate_triplet.py GLOBAL_data_price_close.csv GLOBAL_data_price_open.csv GLOBAL_toll_info.csv
```

Generate the final JSON:

```bash
cd parse
python make_toll_json.py --close GLOBAL_data_price_close.csv --open GLOBAL_data_price_open.csv --info GLOBAL_toll_info.csv --out GLOBAL_network.json
```

## Documentation

- `parse/WORKFLOW.md`: operational pipeline notes.
- `parse/README_SCHEMA.md`: JSON schema explanation.
- `tools/TOPOLOGY_TOOL.md`: design notes for the topology editor.

## License

This project uses a dual-licensing model:

| Type | License | File |
|------|---------|------|
| Code | [AGPL-3.0-or-later](LICENSE) | `LICENSE` |
| Data | [ODbL-1.0](LICENSE-DATA) | `LICENSE-DATA` |

See `NOTICE.md` for detailed attribution and usage information.
