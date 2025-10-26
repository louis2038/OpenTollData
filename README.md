

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

