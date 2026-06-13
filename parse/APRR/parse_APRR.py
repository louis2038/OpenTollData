#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2025-2026 Louis TRIOULEYRE-ROBERJOT
# This file is part of TollData - Open French Highway Toll Database
"""
Parser des tarifs APRR depuis le fichier texte brut extrait du PDF.

Format d'entrée (une ligne par paire de gares, toutes classes sur la même ligne):
    STATION_A STATION_B 123,45 10,00 € 15,00 € 20,00 € 25,00 € 5,00 €

Le problème principal est de séparer STATION_A (gare de départ) de STATION_B
(gare d'arrivée) quand les deux peuvent contenir des espaces.

Stratégie: découverte itérative des noms de gares.
  1. On part d'un bloc évident (gare en un seul mot, ex: ALLAINES)
     et on extrait ses destinations → liste initiale de gares.
  2. On itère: pour chaque ligne, si le préfixe match une gare connue,
     le reste est une nouvelle gare candidate.
  3. Convergence en ~2 itérations (toutes les gares sont trouvées).
  4. Parsing final avec longest-match-first.

Sorties:
  - APRR_data_price_close_2026.csv : tarifs système fermé
  - APRR_data_price_open_2026.csv  : tarifs système ouvert
  - APRR_toll_info.csv             : liste des gares (à compléter manuellement)

Utilisation:
    python parse_APRR.py [--input RAW_FILE] [--output-dir DIR]
"""

import csv
import re
import sys
import unicodedata
from pathlib import Path

# ---------------------------------------------------------------------------
# Gares à ignorer (absentes d'OSM / données inexploitables)
# ---------------------------------------------------------------------------

# Noms canoniques (après mapping) des gares à exclure de tous les CSV de sortie.
# Ces gares n'ont pas de correspondance dans peages_all.csv et ne peuvent pas
# être géolocalisées dans OSM.
IGNORED_STATIONS: set[str] = {
    "CHALONS MOURMELON",
    "LA FOLIE B PARIS",
    "LUSSE",
    "VILLEFRANCHE VILLE",
    "LA BOISSE",
    "GERZAT VILLE",
}


# ---------------------------------------------------------------------------
# Normalisation des noms (convention projet)
# ---------------------------------------------------------------------------


def normalize_name(s: str) -> str:
    """Normalise un nom de station selon la convention TollData."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )
    s = re.sub(r"[^A-Za-z0-9]", " ", s)
    s = re.sub(r"\s+", " ", s)
    s = s.strip()
    return s.upper()


def load_name_mapping(mapping_path: Path) -> dict[str, str]:
    """
    Charge le fichier de mapping APRR -> ASF des noms de gares.

    Le fichier CSV doit avoir les colonnes 'aprr_name' et 'asf_name'
    (délimiteur ';'). Les noms sont déjà normalisés.

    Returns:
        Dict {nom_aprr_normalisé: nom_asf_normalisé}
    """
    mapping = {}
    if not mapping_path.exists():
        print(
            f"  [WARN] Fichier de mapping introuvable: {mapping_path}", file=sys.stderr
        )
        return mapping

    with open(mapping_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            aprr = row["aprr_name"].strip()
            asf = row["asf_name"].strip()
            if aprr and asf:
                mapping[aprr] = asf

    return mapping


def apply_name_mapping(name: str, mapping: dict[str, str]) -> str:
    """
    Applique le mapping APRR -> ASF sur un nom normalisé.

    Si le nom existe dans le mapping, retourne le nom ASF correspondant.
    Sinon, retourne le nom tel quel.
    """
    return mapping.get(name, name)


def fr_to_float_str(x: str) -> str:
    """Convertit une valeur décimale française '12,34' en '12.34'."""
    return x.replace(",", ".")


# ---------------------------------------------------------------------------
# Fusion avec les données OSM (peages_all.csv)
# ---------------------------------------------------------------------------


def _expand_saint(s: str) -> str:
    """Remplace ST/STE par SAINT/SAINTE dans un nom normalisé."""
    parts = s.split()
    result = []
    for p in parts:
        if p == "STE":
            result.append("SAINTE")
        elif p == "ST":
            result.append("SAINT")
        else:
            result.append(p)
    return " ".join(result)


def _strip_peage(s: str) -> str:
    """Retire le préfixe 'PEAGE DE/DES/DU' d'un nom normalisé."""
    for prefix in ["PEAGE DE ", "PEAGE DES ", "PEAGE DU ", "PEAGE "]:
        if s.startswith(prefix):
            return s[len(prefix) :]
    return s


def _levenshtein(s1: str, s2: str) -> int:
    """Distance de Levenshtein entre deux chaînes."""
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (c1 != c2)))
        prev = curr
    return prev[-1]


def load_peages_data(peages_path: Path) -> dict:
    """
    Charge le fichier peages_all.csv et construit un index de lookup.

    Returns:
        Dict avec:
          'by_osm_name': {osm_name: row_dict}
          'lookup': {normalized_variant: osm_name} pour recherche rapide
          'all_osm_names': liste de tous les osm_name
    """
    import csv as _csv

    by_osm_name = {}
    lookup = {}  # normalized_variant -> osm_name

    with open(peages_path, "r", encoding="utf-8") as f:
        reader = _csv.DictReader(f)
        for row in reader:
            osm_name = row["osm_name"]
            by_osm_name[osm_name] = row

            nn = normalize_name(osm_name)
            expanded = _expand_saint(nn)
            stripped = _strip_peage(nn)
            expanded_stripped = _strip_peage(expanded)
            for key in [nn, expanded, stripped, expanded_stripped]:
                if key not in lookup:
                    lookup[key] = osm_name

    return {
        "by_osm_name": by_osm_name,
        "lookup": lookup,
        "all_osm_names": list(by_osm_name.keys()),
    }


def find_osm_match(
    canonical_name: str, peages_data: dict, max_errors: int = 2
) -> str | None:
    """
    Trouve la meilleure correspondance OSM pour un nom canonique.

    Stratégie:
      1. Recherche dans les overrides manuels
      2. Recherche exacte sur les variantes normalisées (ST->SAINT, PEAGE DE)
      3. Recherche floue (Levenshtein <= max_errors) sur les variantes étendues

    Returns:
        Le osm_name correspondant, ou None si pas de match.
    """
    # Correspondances manuelles: noms canoniques dont le nom OSM est
    # trop différent pour être trouvé par fuzzy matching.
    MANUAL_OVERRIDES = {
        "AMBERIEU": "Ambérieu-en-Buguey",
        "CHALONS LA VEUVE": "Châlons en Champagne-La Veuve",
        "CHATENOIS SUD": "Chatenois",
        "PEAGE DE CLERMONT": "Clermont Barrière",
        "GERZAT": "Gerzat Ville",
        "GONDREVILLE NORD": "Gondreville",
        "GONDREVILLE SUD": "Gondreville",
        "SYLANS SUD": "Sylans",
        "VILLEFRANCHE SUR CHER": "Romorantin",
        "CHEMERY": "Selles-sur-Cher",
        "ST ROMAIN SUR CHER": "Saint-Aignan-sur-Cher",
        "MONTREUIL REIMS": "Montreuil-aux-Lions",
    }

    # 0. Override manuel
    if canonical_name in MANUAL_OVERRIDES:
        override = MANUAL_OVERRIDES[canonical_name]
        if override in peages_data["by_osm_name"]:
            return override

    nn = normalize_name(canonical_name)
    expanded = _expand_saint(nn)
    stripped = _strip_peage(nn)
    expanded_stripped = _strip_peage(expanded)

    # 1. Recherche exacte
    for key in [nn, expanded, stripped, expanded_stripped]:
        if key in peages_data["lookup"]:
            return peages_data["lookup"][key]

    # 2. Recherche floue avec variantes étendues
    best_dist = max_errors + 1
    best_name = None

    for osm_name in peages_data["all_osm_names"]:
        onn = normalize_name(osm_name)
        on_exp = _expand_saint(onn)
        on_strip = _strip_peage(onn)
        on_exp_strip = _strip_peage(on_exp)

        for target in [expanded, expanded_stripped]:
            for candidate in [on_exp, on_exp_strip]:
                d = _levenshtein(target, candidate)
                if d < best_dist:
                    best_dist = d
                    best_name = osm_name

    if best_dist <= max_errors:
        return best_name

    return None


# ---------------------------------------------------------------------------
# Parsing du fichier brut
# ---------------------------------------------------------------------------

# Regex pour extraire: texte_stations  distance  price1€  price2€  price3€  price4€  price5€
LINE_RE = re.compile(
    r"^(.+?)\s+"  # text part (station_from + station_to)
    r"(\d+,\d{2})\s+"  # distance
    r"(\d+,\d{2})\s*€\s+"  # price1
    r"(\d+,\d{2})\s*€\s+"  # price2
    r"(\d+,\d{2})\s*€\s+"  # price3
    r"(\d+,\d{2})\s*€\s+"  # price4
    r"(\d+,\d{2})\s*€"  # price5
)

SYSTEME_OUVERT_RE = re.compile(
    r"^(.+?)\s+Système\s+Ouvert\s+"
    r"(\d+,\d{2})\s+"  # distance
    r"(\d+,\d{2})\s*€\s+"  # price1
    r"(\d+,\d{2})\s*€\s+"  # price2
    r"(\d+,\d{2})\s*€\s+"  # price3
    r"(\d+,\d{2})\s*€\s+"  # price4
    r"(\d+,\d{2})\s*€"  # price5
)


def parse_raw_lines(lines: list[str]) -> tuple[list[dict], list[dict]]:
    """
    Parse les lignes brutes en deux listes:
    - close_entries: lignes de péage fermé (deux gares)
    - open_entries: lignes "Système Ouvert" (une gare)

    Returns:
        (close_entries, open_entries) où chaque entry contient
        'text', 'distance', 'prices' (liste de 5 strings)
    """
    close_entries = []
    open_entries = []
    unparsed = []

    for i, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line:
            continue

        # D'abord tester "Système Ouvert"
        m_open = SYSTEME_OUVERT_RE.match(line)
        if m_open:
            open_entries.append(
                {
                    "station": m_open.group(1).strip(),
                    "distance": m_open.group(2),
                    "prices": [m_open.group(j) for j in range(3, 8)],
                    "line_num": i,
                }
            )
            continue

        # Sinon, ligne fermée standard
        m = LINE_RE.match(line)
        if m:
            close_entries.append(
                {
                    "text": m.group(1).strip(),
                    "distance": m.group(2),
                    "prices": [m.group(j) for j in range(3, 8)],
                    "line_num": i,
                }
            )
            continue

        unparsed.append((i, line))

    if unparsed:
        print(f"[WARN] {len(unparsed)} ligne(s) non reconnue(s):", file=sys.stderr)
        for num, txt in unparsed[:10]:
            print(f"  L{num}: {txt[:100]}", file=sys.stderr)

    return close_entries, open_entries


# ---------------------------------------------------------------------------
# Découverte itérative des noms de gares
# ---------------------------------------------------------------------------


def discover_stations(
    close_entries: list[dict], open_entries: list[dict], seed_station: str = None
) -> set[str]:
    """
    Découvre tous les noms de gares par itération.

    Étape 1: trouver une gare "seed" évidente (un seul mot en début de ligne).
    Étape 2: extraire toutes ses destinations → premières gares connues.
    Étape 3: itérer: pour chaque ligne, si le préfixe match une gare connue,
             le reste est une nouvelle gare candidate.

    Args:
        close_entries: liste des entrées fermées (avec champ 'text')
        open_entries: liste des entrées ouvertes (avec champ 'station')
        seed_station: nom de la gare seed (optionnel, auto-détecté sinon)

    Returns:
        Ensemble de tous les noms de gares trouvés
    """
    texts = [e["text"] for e in close_entries]

    # Ajouter les gares des péages ouverts
    open_station_names = {e["station"] for e in open_entries}

    # ---- Trouver le seed ----
    if seed_station is None:
        # Chercher un bloc où le premier mot est unique et suivi d'un
        # second mot différent à chaque ligne → le premier mot est la gare from
        first_words = {}
        for text in texts:
            words = text.split()
            first = words[0]
            if first not in first_words:
                first_words[first] = []
            first_words[first].append(text)

        # Prendre un premier mot qui a beaucoup de lignes et dont le 2e mot varie
        for word, group in sorted(
            first_words.items(), key=lambda x: len(x[1]), reverse=True
        ):
            second_words = set()
            for text in group:
                rest = text[len(word) + 1 :] if len(text) > len(word) + 1 else ""
                if rest:
                    second_words.add(rest.split()[0])
            # Si le 2e mot varie beaucoup, c'est probablement un seul-mot from-station
            if len(second_words) > 10:
                seed_station = word
                break

        if seed_station is None:
            raise RuntimeError("Impossible de trouver une gare seed automatiquement")

    print(f"  Seed station: {seed_station}")

    # ---- Étape 2: extraire destinations du seed ----
    known_stations = set()
    known_stations.add(seed_station)
    known_stations.update(open_station_names)

    for text in texts:
        if text.startswith(seed_station + " "):
            dest = text[len(seed_station) + 1 :]
            known_stations.add(dest)

    print(f"  Après seed: {len(known_stations)} gare(s) connue(s)")

    # ---- Étape 3: itérer ----
    for iteration in range(50):
        new_stations = set()

        # Trier par longueur décroissante pour longest match
        sorted_stations = sorted(known_stations, key=len, reverse=True)

        for text in texts:
            for from_station in sorted_stations:
                if text.startswith(from_station + " "):
                    remainder = text[len(from_station) + 1 :]
                    if remainder and remainder not in known_stations:
                        new_stations.add(remainder)
                    break

        added = new_stations - known_stations
        if not added:
            print(
                f"  Convergence à l'itération {iteration} : {len(known_stations)} gare(s)"
            )
            break
        known_stations.update(added)
        print(
            f"  Itération {iteration}: +{len(added)} gare(s), total {len(known_stations)}"
        )

    return known_stations


def split_from_to(text: str, known_stations: set[str]) -> tuple[str, str] | None:
    """
    Sépare 'GARE_A GARE_B' en (gare_from, gare_to) en utilisant la liste connue.

    Essaie le longest-match-first sur gare_from, vérifie que le reste est connu.

    Returns:
        (from_station, to_station) ou None si impossible à résoudre.
    """
    for from_station in sorted(known_stations, key=len, reverse=True):
        if text.startswith(from_station + " "):
            remainder = text[len(from_station) + 1 :]
            if remainder in known_stations:
                return (from_station, remainder)
    return None


# ---------------------------------------------------------------------------
# Génération des CSV
# ---------------------------------------------------------------------------


def write_close_csv(
    close_entries: list[dict],
    known_stations: set[str],
    name_mapping: dict[str, str],
    output_path: Path,
) -> int:
    """Écrit le CSV des prix fermés."""
    rows = []
    errors = 0

    for entry in close_entries:
        result = split_from_to(entry["text"], known_stations)
        if result is None:
            print(
                f"  [ERR] L{entry['line_num']}: impossible de séparer '{entry['text']}'",
                file=sys.stderr,
            )
            errors += 1
            continue

        from_name, to_name = result
        mapped_from = apply_name_mapping(normalize_name(from_name), name_mapping)
        mapped_to = apply_name_mapping(normalize_name(to_name), name_mapping)
        if mapped_from in IGNORED_STATIONS or mapped_to in IGNORED_STATIONS:
            continue
        rows.append(
            [
                mapped_from,
                mapped_to,
                fr_to_float_str(entry["distance"]),
                fr_to_float_str(entry["prices"][0]),
                fr_to_float_str(entry["prices"][1]),
                fr_to_float_str(entry["prices"][2]),
                fr_to_float_str(entry["prices"][3]),
                fr_to_float_str(entry["prices"][4]),
            ]
        )

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(
            [
                "name_from",
                "name_to",
                "distance",
                "price1",
                "price2",
                "price3",
                "price4",
                "price5",
            ]
        )
        w.writerows(rows)

    if errors:
        print(f"  [WARN] {errors} ligne(s) non résolue(s)", file=sys.stderr)

    return len(rows)


def write_open_csv(
    open_entries: list[dict], name_mapping: dict[str, str], output_path: Path
) -> int:
    """Écrit le CSV des prix ouverts."""
    rows = []

    for entry in open_entries:
        mapped_name = apply_name_mapping(normalize_name(entry["station"]), name_mapping)
        if mapped_name in IGNORED_STATIONS:
            continue
        rows.append(
            [
                mapped_name,
                fr_to_float_str(entry["distance"]),
                fr_to_float_str(entry["prices"][0]),
                fr_to_float_str(entry["prices"][1]),
                fr_to_float_str(entry["prices"][2]),
                fr_to_float_str(entry["prices"][3]),
                fr_to_float_str(entry["prices"][4]),
            ]
        )

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(
            ["name", "distance", "price1", "price2", "price3", "price4", "price5"]
        )
        w.writerows(rows)

    return len(rows)


def write_toll_info_csv(
    known_stations: set[str],
    open_stations: set[str],
    name_mapping: dict[str, str],
    output_path: Path,
    peages_data: dict | None = None,
) -> int:
    """
    Écrit le CSV toll_info avec les gares découvertes.

    Si peages_data est fourni (chargé depuis peages_all.csv), les champs OSM
    sont remplis automatiquement via fuzzy matching. Sinon, ils restent vides.
    """
    rows = []
    seen = set()
    matched_count = 0
    unmatched_names = []

    for name in sorted(known_stations):
        normalized = apply_name_mapping(normalize_name(name), name_mapping)
        if normalized in seen:
            continue  # éviter les doublons après mapping
        seen.add(normalized)
        if normalized in IGNORED_STATIONS:
            continue
        toll_type = "open" if name in open_stations else "close"

        # Chercher la correspondance OSM
        osm_name = ""
        operator_ref = ""
        lat = ""
        lon = ""
        nbs_booth = ""
        booth_node_id = ""

        if peages_data is not None:
            osm_match = find_osm_match(normalized, peages_data)
            if osm_match:
                osm_row = peages_data["by_osm_name"][osm_match]
                osm_name = osm_row["osm_name"]
                operator_ref = osm_row.get("operator_ref", "")
                lat = osm_row.get("lat", "")
                lon = osm_row.get("lon", "")
                nbs_booth = osm_row.get("nbs_booth", "")
                booth_node_id = osm_row.get("booth_node_id", "")
                matched_count += 1
            else:
                unmatched_names.append(normalized)

        rows.append(
            [
                normalized,  # name
                osm_name,  # osm_name
                operator_ref,  # operator_ref
                lat,  # lat
                lon,  # lon
                nbs_booth,  # nbs_booth
                booth_node_id,  # booth_node_id
                "",  # booth_way_id
                toll_type,  # type
                "APRR",  # operator_osm
            ]
        )

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(
            [
                "name",
                "osm_name",
                "operator_ref",
                "lat",
                "lon",
                "nbs_booth",
                "booth_node_id",
                "booth_way_id",
                "type",
                "operator_osm",
            ]
        )
        w.writerows(rows)

    if peages_data is not None:
        print(f"    OSM merge: {matched_count}/{len(rows)} correspondance(s)")
        if unmatched_names:
            print(f"    [WARN] {len(unmatched_names)} gare(s) sans correspondance OSM:")
            for n in unmatched_names:
                print(f"      - {n}")

    return len(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    import argparse

    default_input = Path(__file__).parent / "raw_data" / "aprr_data_class1_2026.txt"
    default_output_dir = Path(__file__).parent
    default_mapping = Path(__file__).parent / "aprr_to_asf_name_mapping.csv"
    default_peages = Path(__file__).parent.parent / "peages_all.csv"

    p = argparse.ArgumentParser(
        description="Parse les tarifs APRR depuis le texte brut vers 3 CSV."
    )
    p.add_argument(
        "--input",
        "-i",
        default=str(default_input),
        help=f"Fichier texte brut (défaut: {default_input})",
    )
    p.add_argument(
        "--output-dir",
        "-o",
        default=str(default_output_dir),
        help=f"Répertoire de sortie (défaut: {default_output_dir})",
    )
    p.add_argument(
        "--seed",
        default=None,
        help="Nom de la gare seed pour la découverte (défaut: auto)",
    )
    p.add_argument(
        "--mapping",
        "-m",
        default=str(default_mapping),
        help=f"Fichier CSV de mapping APRR->ASF (défaut: {default_mapping})",
    )
    p.add_argument(
        "--no-mapping",
        action="store_true",
        help="Désactiver le mapping APRR->ASF (utiliser les noms bruts)",
    )
    p.add_argument(
        "--peages",
        default=str(default_peages),
        help=f"Fichier CSV des péages OSM (défaut: {default_peages})",
    )
    p.add_argument(
        "--no-peages",
        action="store_true",
        help="Désactiver la fusion avec peages_all.csv (champs OSM vides)",
    )
    p.add_argument(
        "--forceinfo",
        action="store_true",
        help="Régénérer APRR_toll_info.csv (par défaut ce fichier n'est pas écrasé).",
    )
    args = p.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)

    if not input_path.exists():
        print(f"Erreur: fichier introuvable: {input_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Lecture de {input_path}...")
    lines = input_path.read_text(encoding="utf-8").splitlines()
    print(f"  {len(lines)} ligne(s) lue(s)")

    # ---- 1. Parser les lignes brutes ----
    print("\nParsing des lignes brutes...")
    close_entries, open_entries = parse_raw_lines(lines)
    print(f"  {len(close_entries)} entrée(s) fermée(s)")
    print(f"  {len(open_entries)} entrée(s) ouverte(s)")

    # ---- 2. Découvrir les gares ----
    print("\nDécouverte des gares...")
    known_stations = discover_stations(
        close_entries, open_entries, seed_station=args.seed
    )
    open_station_names = {e["station"] for e in open_entries}
    close_station_names = known_stations - open_station_names

    print(f"\n  Résumé:")
    print(f"    Gares fermées : {len(close_station_names)}")
    print(f"    Gares ouvertes: {len(open_station_names)}")
    print(f"    Total         : {len(known_stations)}")

    # ---- 3. Charger le mapping APRR -> ASF ----
    name_mapping = {}
    if not args.no_mapping:
        mapping_path = Path(args.mapping)
        print(f"\nChargement du mapping {mapping_path.name}...")
        name_mapping = load_name_mapping(mapping_path)
        print(f"  {len(name_mapping)} correspondance(s) chargée(s)")
    else:
        print("\nMapping APRR->ASF désactivé (noms bruts)")

    # ---- 3b. Charger les données OSM (peages_all.csv) ----
    peages_data = None
    if args.forceinfo and not args.no_peages:
        peages_path = Path(args.peages)
        if peages_path.exists():
            print(f"\nChargement des données OSM ({peages_path.name})...")
            peages_data = load_peages_data(peages_path)
            print(f"  {len(peages_data['all_osm_names'])} gare(s) OSM chargée(s)")
        else:
            print(
                f"\n  [WARN] Fichier peages_all.csv introuvable: {peages_path}",
                file=sys.stderr,
            )
            print("  Les champs OSM seront vides dans toll_info.")
    elif not args.forceinfo:
        print(
            "\nToll info: APRR_toll_info.csv ne sera pas régénéré (utiliser --forceinfo pour forcer)"
        )
    else:
        print("\nFusion OSM désactivée (champs OSM vides)")

    # ---- 4. Vérifier que tout se parse ----
    print("\nVérification du parsing...")
    success = 0
    fail = 0
    for entry in close_entries:
        result = split_from_to(entry["text"], known_stations)
        if result:
            success += 1
        else:
            fail += 1
    print(f"  Fermé: {success} OK, {fail} échec(s)")
    if fail > 0:
        print(
            f"  [WARN] {fail} ligne(s) ne peuvent pas être séparées!", file=sys.stderr
        )

    # ---- 5. Écrire les CSV ----
    close_csv = output_dir / "APRR_data_price_close_2026.csv"
    open_csv = output_dir / "APRR_data_price_open_2026.csv"
    info_csv = output_dir / "APRR_toll_info.csv"

    print(f"\nÉcriture des fichiers CSV...")

    n_close = write_close_csv(close_entries, known_stations, name_mapping, close_csv)
    print(f"  -> {close_csv.name} ({n_close} lignes)")

    n_open = write_open_csv(open_entries, name_mapping, open_csv)
    print(f"  -> {open_csv.name} ({n_open} lignes)")

    if args.forceinfo:
        n_info = write_toll_info_csv(
            known_stations, open_station_names, name_mapping, info_csv, peages_data
        )
        print(f"  -> {info_csv.name} ({n_info} gares)")
    else:
        print(f"  -- {info_csv.name} non modifié (pas de --forceinfo)")

    print(f"\nTerminé!")


if __name__ == "__main__":
    main()
