# TollData - Open French Highway Toll Database

---

## License

This project uses a **dual-licensing model**:

| Type | License | File |
|------|---------|------|
| **Code** (Python scripts) | [AGPL-3.0-or-later](LICENSE) | `LICENSE` |
| **Data** (CSV, JSON, TXT) | [ODbL-1.0](LICENSE-DATA) | `LICENSE-DATA` |

See [NOTICE.md](NOTICE.md) for detailed attribution and usage information.

---

# Context

This reposetory was created to build an open data price for toll price in french first, we will see after for the next country.

Because every way the price change, the operator publish their price with ugly pdf format, the repo aims to build an automated workflow to transform this pdf in used data. 

When i means usable data, i means of course all the price between booth, but assiocied with the good node or way in Open Street Map and the localisation of node. 

This repository provides open toll price data for French highways, with plans to expand to other countries.

Highway operators frequently update their pricing, but publish this information in PDF format that is difficult to use in pratical. This project automates the conversion of these PDFs into structured, usable data.

The output data includes:
- Toll prices between entry/exit points
- Associated OpenStreetMap nodes and ways
- Precise geographic coordinates of toll booths

The project aims to build a free website to consult this information easily.

# Progress

Data processing status by operator:

**Completed:**
- AREA
- ASF (page 1)

**In Progress:**
- ASF

# JSON Data Format

The output JSON follows a highly structured format:

```json
{
    "date": "26/09/2025",
    "version": "1.0",
    "name": "price_format",
    "list_of_operator": [
        "AREA"
    ],
    "list_of_toll": [
        "AIGUEBELETTE",
        "AIX NORD",
        "AIX SUD",
        "AITON",
        "CHIGNIN BARRIERE"
    ],
    "currency": "EUR",
    "networks": [
        {
            "network_name": "component_1",
            "tolls": [
                "AIGUEBELETTE",
                "AIX NORD",
                "AIX SUD"
            ],
            "connection": {
                "AIGUEBELETTE": {
                    "AIX NORD": {
                        "distance": "24",
                        "price": {
                            "class_1": "3.5",
                            "class_2": "5.4",
                            "class_3": "7.5",
                            "class_4": "10.1",
                            "class_5": "1.6"
                        }
                    },
                    "AIX SUD": {
                        "distance": "17",
                        "price": {
                            "class_1": "2.9",
                            "class_2": "4.4",
                            "class_3": "6.2",
                            "class_4": "8.3",
                            "class_5": "1.2"
                        }
                    }
                },
                "AIX NORD": {
                    ...
                },
                "AIX SUD": {
                    ...
                }
            }
        },
        {
            "network_name": "component_2",
            "tolls": [
                "AITON",
                "CHIGNIN BARRIERE"
            ],
            "connection": {
                ...
            }
        }
    ],

    "toll_description": {
        "AIGUEBELETTE": {
            "operator_ref": "3007",
            "lat": "45.5768820",
            "lon": "5.7992485",
            "operator": "AREA",
            "type": "close",
            "node_id": [
                "36675385",
                "267138475"
            ],
            "ways_id": []
        },
        ...
    },
    "open_toll_price": {
        "CHESNES": {
            "distance": "19",
            "price": {
                "class_1": "2.3",
                "class_2": "3.5",
                "class_3": "5.6",
                "class_4": "6.9",
                "class_5": "1.1"
            }
        },
        ...
    }
}
```


# CSV Data Format

## Closed Toll Price Data

```
name_from  name_to  distance  price1  price2  price3  price4  price5
```

This format represents toll prices between two toll stations (closed system).

## Open Toll Price Data

```
name  distance  price1  price2  price3  price4  price5
```

This format represents toll prices for open systems (flat fee).

## Toll Information

```
name  osm_name  operator_ref  lat  lon  nbs_booth  booth_node_id  booth_way_id  type  operator_osm
```

This describes each toll booth, enriched with metadata coming from OpenStreetMap.

---

# `/parse` Folder

Contains utility scripts used to parse and process operator data and OSM data.

---

# Workflow

1. **Select an operator**

2. **Create a `.csv` file for closed toll prices**
   It must follow the structure:

   ```csv
   name_from,name_to,distance,price1,price2,price3,price4,price5
   ...
   ```

3. **Create a `.csv` file listing toll station names**
   It must follow:

   ```csv
   name
   ...
   ```

   All station names **must be normalized** using the following function:

   ```python
   import re
   import unicodedata

   def normalize_name(s: str) -> str:
       if not s:
           return ""
       s = unicodedata.normalize("NFKC", s)
       s = "".join(
           c for c in unicodedata.normalize("NFD", s)
           if unicodedata.category(c) != "Mn"
       )
       s = re.sub(r"[^A-Za-z0-9]", " ", s)
       s = re.sub(r"\s+", " ", s)
       s = s.strip()
       return s.upper()
   ```

   > `name` is used as a unique primary key.
   > Two different stations must **never** normalize to the same name.

4. **Retrieve toll booths from OpenStreetMap**

   You can use the `request_overpass_turbo.py` script with a query such as:

   ```
   [out:json][timeout:180];
   area[name="France"][boundary=administrative][admin_level=2]->.searchArea;
   node["barrier"="toll_booth"]["operator"="AREA"](area.searchArea);
   out body;
   >;
   out skel qt;
   ```

5. **Convert Overpass Turbo results into CSV**

   Use `overpass_request_out_to_csv.py` to generate a CSV similar to:

   ```
   osm_name            operator_ref  lat         lon         nbs_booth  booth_node_id
   Voreppe Barrière    3087          45.2831859  5.6216873   2          [126236, 136834]
   Moirans             3084          45.3200799  5.6075430   2          [137090, 258027361]
   Tullins             3095          45.2870178  5.5218684   2          [137232, 36715162]
   ```

6. **Merge operator data with OSM data**

   Use the script `merge_overpass_data_with_operator_data.py` to combine:

   * the station name list
   * the OSM toll booth CSV

   Example input:

   ```csv
   name
   ST MARTIN BELLEVUE A41 N
   ST PIERRE BELLEVILLE
   STE MARIE DE CUINES
   ```

   Example output:

   ```
   name;osm_name;operator_ref;lat;lon;nbs_booth;booth_node_id;booth_way_id;type;operator_osm
   ST QUENTIN FAL BRETELLE;;;;;;;;;
   ISLE D ABEAU CENTRE;L'Isle-d'Abeau Centre;3003;45.605103;5.2344726;2;[19224143, 267571099];;;
   BOURGOIN;Bourgoin;3004;45.5822626;5.3002391;2;[36713429, 261946952];;;
   ```

   Some entries may remain incomplete (name mismatch, complexity, etc.).

   **Note:** Some operator entries may represent special cases.
   For example, in AREA, `_3400 SYSTEME OUVERT_` corresponds to no actual toll station, but indicates that the linked toll uses an **open** pricing system.
   In this case:

   * set `type = open`
   * add its price to the **open** price CSV

7. **Manual refinement**

   Use the OSM website or any mapping tool to:

   * identify missing IDs
   * validate booth locations
   * adjust metadata

   The final goal is to obtain **three complete files**:

   ✅ Open toll prices
   ✅ Closed toll prices
   ✅ Toll booth metadata (OSM-enriched)

8. **Generate the aggregated JSON**

   Use:

   ```
   make_toll_json.py
   ```

   This produces a JSON structured like `price_format.json`.

---

# All specificity for operator :

## AREA 

In progress

## ASF

The workflow involves creating one script per page to process the raw data.

The dataset contains many unused toll booths. You need to explore each booth using OSM to determine whether it should be included.

Once relevant booths are identified, download the toll data using Overpass Turbo, then use the merge scripts following the standard workflow described above.

The script development is the most challenging part. You can use the completed page1 script as a reference implementation.

# Additional Features

Some OSM ways may be used by multiple relations (and thus multiple possible prices).
If you want to compute:

* the average toll cost per way
* the minimal toll cost per way

…you can use:

```
make_by_way_with_json_price_and_overpass.py
```

It outputs a CSV that can then be used to enrich a routing engine with cost estimates.

