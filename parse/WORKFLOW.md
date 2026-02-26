# TollData Pipeline Workflow

This document describes the end-to-end pipeline for converting French highway
toll operator PDF price tables into structured, validated, OSM-enriched open
data (CSV triplets and JSON).

## Overview

```
PDF source data
      |
      v
[1] Text extraction (pdf_to_txt.py)
      |
      v
[2] Per-operator parsing (parse_APRR.py / parse_AREA.py / ASF page scripts)
      |
      v  produces per-operator CSV "triplet"
[3] OSM data acquisition (request_overpass_turbo.py -> overpass_request_out_to_csv.py)
      |
      v
[4] OSM merge (merge_overpass_data_with_operator_data.py or built-in matching)
      |
      v  toll_info enriched with lat/lon/node_id/ways_id
[5] Manual refinement (fill missing OSM IDs, verify coordinates, set type)
      |
      v
[6] Per-operator triplet validation (validate_triplet.py)
      |
      v
[7] Global merge across operators (meta_global.py)
      |
      v
[8] Global triplet validation (validate_triplet.py on GLOBAL_* files)
      |
      v
[9] JSON generation (make_toll_json.py)
      |
      v
[10] JSON validation (validate_toll_json.py)
      |
      v
[11] Description JSON extraction (make_toll_desc_json.py)  [optional]
      |
      v
[12] Per-way cost estimation (make_by_way_with_json_price_and_overpass.py)  [optional]
```

## CSV Triplet Format

Every operator (and the global merge) produces three CSV files. Delimiter is
`;`, decimal separator is `.`.

### `*_data_price_close.csv`

Closed-system toll prices (entry-to-exit pairs).

| Column     | Description                          |
|------------|--------------------------------------|
| `name_from`| Departure station (normalized name)  |
| `name_to`  | Arrival station (normalized name)    |
| `distance` | Distance in km                       |
| `price1`   | Class 1 price (light vehicles)       |
| `price2`   | Class 2 price                        |
| `price3`   | Class 3 price                        |
| `price4`   | Class 4 price                        |
| `price5`   | Class 5 price (heavy trucks 3+ axles)|

### `*_data_price_open.csv`

Open-system toll prices (flat fee per station).

| Column     | Description                          |
|------------|--------------------------------------|
| `name`     | Station name (normalized)            |
| `distance` | Distance in km                       |
| `price1`   | Class 1 price                        |
| `price2`–`price5` | Classes 2–5 prices           |

### `*_toll_info.csv`

Station metadata enriched with OpenStreetMap data.

| Column          | Description                              |
|-----------------|------------------------------------------|
| `name`          | Normalized station name (primary key)    |
| `osm_name`      | Name as it appears in OSM                |
| `operator_ref`  | Operator reference code                  |
| `lat`           | Latitude (barycenter of booth nodes)     |
| `lon`           | Longitude (barycenter of booth nodes)    |
| `nbs_booth`     | Number of toll booths                    |
| `booth_node_id` | OSM node IDs (comma-separated list)      |
| `booth_way_id`  | OSM way IDs (comma-separated list)       |
| `type`          | `open` or `close`                        |
| `operator_osm`  | Operator as tagged in OSM                |

## Name Normalization

Station names are the primary key across all files. They are normalized via
`normalize_name()`:

1. Unicode NFKC normalization
2. Strip diacritics (accented characters -> ASCII)
3. Replace non-alphanumeric characters with spaces
4. Collapse consecutive spaces
5. Convert to UPPERCASE

When station names differ between operators for the same physical toll, they
must be unified. ASF names are the reference. APRR uses
`aprr_to_asf_name_mapping.csv` (47 entries) for this purpose.

## Scripts Reference

### Per-Operator Parsers

#### `APRR/parse_APRR.py`

Parses raw text extracted from APRR PDF toll price tables. Handles the key
challenge of splitting station pairs where both names may contain spaces
(e.g., `"STATION A STATION B 123,45 10,00 ..."`).

Uses an iterative station discovery algorithm seeded from a single-word station.
Includes built-in OSM matching via `peages_all.csv` with multi-strategy fuzzy
matching (exact, ST/SAINT normalization, PEAGE DE prefix, Levenshtein).

```
python parse_APRR.py [-i RAW_FILE] [-m MAPPING_CSV] [--peages PEAGES_CSV] [--no-peages]
```

**Inputs:** `raw_data/aprr_raw.txt`, `aprr_to_asf_name_mapping.csv`, `../peages_all.csv`
**Outputs:** `APRR_data_price_close_2026.csv`, `APRR_data_price_open_2026.csv`, `APRR_toll_info.csv`

#### `AREA/parse_AREA.py`

Parses AREA raw data from `AREA_brut_data.txt`.

**Outputs:** `AREA_data_price_close.csv`, `AREA_data_price_open.csv`, `AREA_toll_info.csv`

#### ASF Pipeline (`ASF/`)

ASF parsing is split across per-page scripts (one subdirectory per PDF page
group: `page1/`, `page2/`, etc.). These are orchestrated by:

- **`ASF/run_all_page_scripts.py`** -- Runs all per-page parsing scripts sequentially
- **`ASF/meta_asf.py`** -- Merges all per-page CSVs into the final ASF triplet

See `ASF/README_META_SCRIPTS.md` and `ASF/UTILISATION.md` for details.

**Outputs:** `ASF_data_price_close_2025.csv`, `ASF_data_price_open_2025.csv`, `ASF_toll_info.csv`

### OSM Data Acquisition

#### `request_overpass_turbo.py`

Queries the Overpass API for all French toll booth nodes/ways and saves the
raw JSON response.

#### `overpass_request_out_to_csv.py`

Converts the Overpass JSON output into an aggregated CSV (`peages_all.csv`):
one row per toll station, with barycenter coordinates and comma-separated
booth node/way IDs.

**Output:** `peages_all.csv` (618 entries covering all French toll booths in OSM)

### OSM Merge

#### `merge_overpass_data_with_operator_data.py`

Merges operator station names with OSM data using Levenshtein fuzzy matching.
Unmatched names get empty OSM fields for manual completion.

```
python merge_overpass_data_with_operator_data.py <osm_file> <names_file> <output_file> [--max-errors N]
```

Note: APRR's parser (`parse_APRR.py`) has this functionality built-in via its
`--peages` flag, using a more sophisticated multi-strategy matching approach.

### Meta / Merge Scripts

#### `meta_global.py`

Merges per-operator triplets (ASF + AREA + APRR) into a single global triplet.
Handles deduplication:

- **Close/Open prices:** deduplicated on station name pair/name
- **Toll info:** deduplicated on station name with OSM ID conflict detection

```
python meta_global.py
```

**Inputs:** Hardcoded paths to all three operators' triplets
**Outputs:** `GLOBAL_data_price_close.csv`, `GLOBAL_data_price_open.csv`, `GLOBAL_toll_info.csv`

### Validation Scripts

#### `validate_triplet.py`

Validates internal consistency of a CSV triplet: every station in the price
files must exist in toll_info, and every station in toll_info must appear in
at least one price file.

```
python validate_triplet.py <close_csv> <open_csv> <toll_info_csv>
```

Exit code 0 on success, 1 on failure.

#### `validate_toll_json.py`

Validates a toll network JSON file against both a JSON Schema
(`toll_network_schema.json`) and additional cross-field constraints:

- Toll name format (uppercase ASCII + digits + spaces + underscores + hyphens)
- `toll_description` keys match `list_of_toll`
- Every toll has at least one OSM node_id or ways_id
- Operator consistency, type/network membership checks
- Price format validation (class_1 through class_5, numeric strings)

```
python validate_toll_json.py <json_file> [--schema SCHEMA] [--summary] [-v]
```

### JSON Generation

#### `make_toll_json.py`

Builds the structured toll network JSON from a validated CSV triplet. Performs
cross-validation before generating. Automatically discovers connected
components in the closed-system toll graph to build "networks".

```
python make_toll_json.py --close <close.csv> --open <open.csv> --info <info.csv> [--out FILE] [--version V] [--name N]
```

#### `make_toll_desc_json.py`

Extracts a lightweight "description-only" JSON from a full toll network JSON,
stripping out connection maps and price data. Useful for applications that
only need toll locations and metadata.

```
python make_toll_desc_json.py <input_json> [output_json]
```

### Utility Scripts

#### `pdf_to_txt.py`

Extracts text from PDF files using PyPDF2.

#### `make_by_way_with_json_price_and_overpass.py`

Computes per-OSM-way toll cost estimates by finding shortest paths through the
road graph and averaging prices across toll relations. Outputs JSON and/or CSV.

## Typical Full Run

```bash
# 1. Parse each operator (if re-parsing from raw data)
cd parse/APRR && python parse_APRR.py
cd parse/AREA && python parse_AREA.py
cd parse/ASF  && python run_all_page_scripts.py && python meta_asf.py

# 2. Validate each operator's triplet
cd parse
python validate_triplet.py APRR/APRR_data_price_close_2026.csv APRR/APRR_data_price_open_2026.csv APRR/APRR_toll_info.csv
python validate_triplet.py AREA/AREA_data_price_close.csv AREA/AREA_data_price_open.csv AREA/AREA_toll_info.csv
python validate_triplet.py ASF/ASF_data_price_close_2025.csv ASF/ASF_data_price_open_2025.csv ASF/ASF_toll_info.csv

# 3. Global merge
python meta_global.py

# 4. Validate global triplet
python validate_triplet.py GLOBAL_data_price_close.csv GLOBAL_data_price_open.csv GLOBAL_toll_info.csv

# 5. Generate JSON
python make_toll_json.py --close GLOBAL_data_price_close.csv --open GLOBAL_data_price_open.csv --info GLOBAL_toll_info.csv --out toll_network.json

# 6. Validate JSON
python validate_toll_json.py toll_network.json

# 7. (Optional) Generate description-only JSON
python make_toll_desc_json.py toll_network.json toll_network_desc.json
```

## Current Operators

| Operator | Status    | Data Year | Stations | Close Pairs | Open Stations |
|----------|-----------|-----------|----------|-------------|---------------|
| ASF      | Complete  | 2025      | 389      | 9,602       | 23            |
| AREA     | Complete  | N/A       | 52       | 950         | 7             |
| APRR     | Complete  | 2026      | 173      | 21,110      | 12            |
| **GLOBAL** | **Merged** | **Mixed** | **448** | **29,952** | **42**       |

## Adding a New Operator

1. Create a directory `parse/<OPERATOR>/`
2. Extract raw text from the operator's PDF
3. Write a parser script that produces the three CSV files
4. If station names differ from existing operators, create a name mapping CSV
5. Merge with OSM data (via `merge_overpass_data_with_operator_data.py` or built-in)
6. Add any unmatched stations to an `IGNORED_STATIONS` set or find them in OSM
7. Validate the triplet with `validate_triplet.py`
8. Add the new operator's files to `meta_global.py`
9. Re-run the global merge and downstream steps (JSON generation, validation)
