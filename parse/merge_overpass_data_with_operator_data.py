import pandas as pd
import unicodedata
import re
from difflib import SequenceMatcher
from argparse import ArgumentParser

def normalize_name(s: str) -> str:
    if not s:
        return ""
    # Normalisation Unicode
    s = unicodedata.normalize("NFKC", s)
    # Retire les diacritiques (accents)
    s = "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )
    # Remplace tout ce qui n'est PAS lettre ou chiffre par un espace
    s = re.sub(r"[^A-Za-z0-9]", " ", s)
    # Remplace plusieurs espaces par un seul
    s = re.sub(r"\s+", " ", s)
    # Trim
    s = s.strip()
    # Uppercase
    return s.upper()

def similarity(a, b):
    """Calcule la similarité entre deux chaînes"""
    return SequenceMatcher(None, a, b).ratio()

def levenshtein_distance(s1, s2):
    """Calcule la distance de Levenshtein entre deux chaînes"""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]

def find_best_match(target_name, osm_names, max_errors=2):
    """Trouve la meilleure correspondance pour un nom donné avec une tolérance de fautes"""
    target_normalized = normalize_name(target_name)
    best_match = None
    best_distance = float('inf')
    
    for osm_name in osm_names:
        osm_normalized = normalize_name(osm_name)
        distance = levenshtein_distance(target_normalized, osm_normalized)
        
        if distance <= max_errors and distance < best_distance:
            best_distance = distance
            best_match = osm_name
    
    return best_match, best_distance

def merge_csv_files(osm_file, names_file, output_file, max_errors=2):
    """Fusionne les deux fichiers CSV"""
    
    # Lire les fichiers CSV avec le délimiteur ; et forcer booth_node_id en string
    osm_df = pd.read_csv(osm_file, dtype={'booth_node_id': str})
    names_df = pd.read_csv(names_file)
    
    # Créer le DataFrame de sortie avec toutes les colonnes nécessaires
    merged_data = []
    
    # Pour chaque nom officiel, chercher une correspondance OSM
    for _, row in names_df.iterrows():
        official_name = row['name']
        
        # Chercher la meilleure correspondance dans les noms OSM (max 2 fautes)
        best_match, distance = find_best_match(official_name, osm_df['osm_name'].tolist(), max_errors=max_errors)
        
        if best_match:
            # Trouver la ligne correspondante dans le DataFrame OSM
            osm_row = osm_df[osm_df['osm_name'] == best_match].iloc[0]
            
            merged_row = {
                'name': official_name,
                'osm_name': osm_row['osm_name'],
                'operator_ref': osm_row['operator_ref'],
                'lat': osm_row['lat'],
                'lon': osm_row['lon'],
                'nbs_booth': osm_row['nbs_booth'],
                'booth_node_id': osm_row['booth_node_id'],  # Déjà en string grâce au dtype
                'booth_way_id': '',
                'type': '',
                'operator_osm': ''
            }
        else:
            # Aucune correspondance trouvée, créer une ligne avec le nom officiel seulement
            merged_row = {
                'name': official_name,
                'osm_name': '',
                'operator_ref': '',
                'lat': '',
                'lon': '',
                'nbs_booth': '',
                'booth_node_id': '',
                'booth_way_id': '',
                'type': '',
                'operator_osm': ''
            }
        
        merged_data.append(merged_row)
    
    # Créer le DataFrame final
    merged_df = pd.DataFrame(merged_data)
    
    # Sauvegarder le fichier fusionné
    merged_df.to_csv(output_file, sep=';', index=False)
    
    print(f"Fichier fusionné créé : {output_file}")
    print(f"Nombre total de noms officiels : {len(names_df)}")
    print(f"Nombre de correspondances trouvées : {len([row for row in merged_data if row['osm_name']])}")

# Exemple d'utilisation
if __name__ == "__main__":
    parser = ArgumentParser(description="Fusionne les données OSM avec les noms officiels de stations")
    parser.add_argument("osm_file", help="Fichier CSV contenant les données OSM")
    parser.add_argument("names_file", help="Fichier CSV contenant les noms officiels")
    parser.add_argument("output_file", help="Fichier CSV de sortie")
    parser.add_argument(
        "--max-errors",
        type=int,
        default=2,
        help="Nombre maximum d'erreurs tolérées (distance de Levenshtein) lors de la correspondance des noms (défaut: 2)"
    )
    
    args = parser.parse_args()
    
    merge_csv_files(args.osm_file, args.names_file, args.output_file, max_errors=args.max_errors)

"""
osm_file format:
osm_name,operator_ref,lat,lon,nbs_booth,booth_node_id
Voreppe Barrière,3087,45.2831859,5.6216873,2,"[126236, 136834]"
Moirans,3084,45.3200799,5.6075430,2,"[137090, 258027361]"
Tullins,3095,45.2870178,5.5218684,2,"[137232, 36715162]"

names_file format:
name
ST MARTIN BELLEVUE A41 N
ST PIERRE BELLEVILLE
STE MARIE DE CUINES
"""