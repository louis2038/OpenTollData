# TollData Workflow

This page is the short operational workflow for the `parse/` pipeline. The main project overview is in `../README.md`.

## Pipeline Map

```text
operator source documents
  -> per-operator parser
  -> operator price CSVs
  -> toll_info enrichment and manual review
  -> global price merge
  -> validation
  -> JSON generation
```

## 1. Parse Operator Data

Each operator has its own directory and parser because the source documents are not standardized.

```text
ASF/        ASF page-based parser workflow
APRR/       APRR parser and APRR -> ASF name mapping
AREA/       AREA parser
COFIROUTE/  COFIROUTE parser and mapping
```

Expected price outputs per operator:

```text
<OPERATOR>_data_price_close_<YEAR>.csv
<OPERATOR>_data_price_open_<YEAR>.csv
```

Operator parsers should not overwrite curated `*_toll_info.csv` files by default. If a script can rebuild toll metadata, this must be behind an explicit option such as `--forceinfo` or `--newinfo`.

## 2. Maintain Toll Metadata

`toll_info` links normalized station names to OpenStreetMap data.

```text
name;osm_name;operator_ref;lat;lon;nbs_booth;booth_node_id;booth_way_id;type;operator_osm
```

This file is sensitive because it contains manual decisions:

- station identity;
- OSM matching;
- booth coordinates;
- `open` or `close` classification;
- duplicate and alias resolution.

The global curated file is:

```text
GLOBAL_toll_info.csv
```

Do not regenerate it casually. Fixing a wrong station identity in several operator files is error-prone; prefer editing the curated global metadata and using validation to find missing entries.

## 3. Merge Global Prices

From `parse/`:

```bash
python meta_global.py
```

Default behavior:

- reads operator close/open price files;
- writes `GLOBAL_data_price_close.csv`;
- writes `GLOBAL_data_price_open.csv`;
- keeps existing `GLOBAL_toll_info.csv` unchanged.

To explicitly rebuild global toll metadata from operator `*_toll_info.csv` files:

```bash
python meta_global.py --forceinfo
```

Use `--forceinfo` only when you really want to rebuild metadata and review the result.

## 4. Validate CSV Consistency

```bash
python validate_triplet.py GLOBAL_data_price_close.csv GLOBAL_data_price_open.csv GLOBAL_toll_info.csv
```

The validator checks:

- every price station exists in `toll_info`;
- `open` prices point to `type=open` stations;
- `close` prices point to `type=close` stations;
- numeric values are valid;
- OSM node IDs are not reused inconsistently.

Validation errors are usually data-quality issues, not just script bugs.

## 5. Generate JSON

```bash
python make_toll_json.py \
  --close GLOBAL_data_price_close.csv \
  --open GLOBAL_data_price_open.csv \
  --info GLOBAL_toll_info.csv \
  --out GLOBAL_network.json
```

Then validate:

```bash
python validate_toll_json.py GLOBAL_network.json
```

Optional description-only export:

```bash
python make_toll_desc_json.py GLOBAL_network.json GLOBAL_network_desc.json
```

## 6. Add A New Operator

Minimal checklist:

1. Create `parse/<OPERATOR>/`.
2. Add raw source data or extracted text.
3. Write a parser that outputs close/open price CSVs.
4. Normalize names with the project convention.
5. Create a name mapping file if the operator uses aliases.
6. Match stations to OSM, but keep manual review possible.
7. Validate operator files when a reliable `toll_info` exists.
8. Add the operator price files to `meta_global.py`.
9. Re-run global merge and validation.

## Name Normalization

Station names are used as keys. Keep them uppercase ASCII-like and stable.

Common normalization rules:

1. Unicode NFKC normalization.
2. Strip accents.
3. Replace non-alphanumeric characters with spaces.
4. Collapse repeated spaces.
5. Convert to uppercase.

The goal is not only clean text. The goal is stable identity across operators.

## Related Docs

- `../README.md`: project overview and data-quality goals.
- `README_SCHEMA.md`: JSON structure and validation rules.
- `../tools/TOPOLOGY_TOOL.md`: next topology/debugging tool.
