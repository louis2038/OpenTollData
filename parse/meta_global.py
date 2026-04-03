#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2025-2026 Louis TRIOULEYRE-ROBERJOT
# This file is part of TollData - Open French Highway Toll Database
"""
Script de fusion globale des triplets ASF, AREA, APRR et COFIROUTE.

Ce script fusionne les fichiers finaux de différents opérateurs pour créer
un triplet global de données de péage.

Utilisation:
    python meta_global.py              # fusion seule
    python meta_global.py --recompile  # re-exécute les parsers puis fusionne
"""

import argparse
import csv
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def recompile_operators(base_dir: Path) -> None:
    """
    Ré-exécute les scripts de parsing de chaque opérateur pour régénérer
    leurs fichiers CSV avant la fusion.

    Ordre d'exécution:
        1. ASF       — meta_asf.py              (depuis parse/ASF/)
        2. AREA      — parse_AREA.py            (depuis parse/AREA/)
        3. APRR      — parse_APRR.py            (depuis parse/APRR/)
        4. COFIROUTE — parse_cofiroute_close.py (depuis parse/COFIROUTE/all/)

    Lève SystemExit en cas d'échec d'un des scripts.
    """
    operators = [
        {
            "name": "ASF",
            "cmd": [sys.executable, "meta_asf.py"],
            "cwd": base_dir / "ASF",
        },
        {
            "name": "AREA",
            "cmd": [
                sys.executable,
                "parse_AREA.py",
                "AREA_brut_data.txt",
                "-o",
                "AREA_data_price_close.csv",
                "--delimiter",
                ";",
            ],
            "cwd": base_dir / "AREA",
        },
        {
            "name": "APRR",
            "cmd": [sys.executable, "parse_APRR.py"],
            "cwd": base_dir / "APRR",
        },
        {
            "name": "COFIROUTE",
            "cmd": [sys.executable, "parse_cofiroute_close.py"],
            "cwd": base_dir / "COFIROUTE" / "all",
        },
    ]

    print("\n" + "=" * 80)
    print("  RECOMPILATION DES OPERATEURS")
    print("=" * 80)

    for op in operators:
        print(f"\n{'─' * 40}")
        print(f"  Recompilation {op['name']}...")
        print(f"  Commande: {' '.join(op['cmd'])}")
        print(f"  Répertoire: {op['cwd']}")
        print(f"{'─' * 40}\n")

        result = subprocess.run(op["cmd"], cwd=op["cwd"])

        if result.returncode != 0:
            print(
                f"\n❌ ERREUR: La recompilation de {op['name']} a échoué "
                f"(code retour: {result.returncode})"
            )
            sys.exit(1)

        print(f"\n  ✅ {op['name']} recompilé avec succès")

    print("\n" + "=" * 80)
    print("  ✅ RECOMPILATION DE TOUS LES OPERATEURS TERMINÉE")
    print("=" * 80)


def detect_delimiter(file_path: str) -> str:
    """
    Détecte automatiquement le délimiteur d'un fichier CSV.

    Args:
        file_path: Chemin du fichier CSV

    Returns:
        Le délimiteur détecté (';' ou ',')
    """
    with open(file_path, "r", encoding="utf-8") as f:
        first_line = f.readline()
        if ";" in first_line:
            return ";"
        elif "," in first_line:
            return ","
        else:
            return ";"


def normalize_osm_id_list(value: str) -> str:
    """
    Normalise une liste d'IDs OSM sérialisée en texte.

    Exemple:
        "[1, 2, 3]" -> "[1,2,3]"
        "[1,2, 3]" -> "[1,2,3]"

    Si la valeur n'est pas une liste entre crochets, on retourne la version trim.
    """
    if value is None:
        return ""

    s = value.strip()
    if not s:
        return ""

    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        if not inner:
            return "[]"
        parts = [p.strip() for p in inner.split(",") if p.strip()]
        return "[" + ",".join(parts) + "]"

    return s


def normalize_text(value: Optional[str]) -> str:
    """Normalise une valeur texte simple."""
    return value.strip() if isinstance(value, str) else ""


def normalize_number(value: Optional[str]) -> str:
    """Normalise une valeur numérique texte en supprimant les zéros inutiles."""
    text = normalize_text(value)
    if not text:
        return ""

    try:
        number = float(text.replace(",", "."))
    except ValueError:
        return text

    if number.is_integer():
        return str(int(number))

    return f"{number:.10f}".rstrip("0").rstrip(".")


def normalize_row(row: Dict[str, str]) -> Dict[str, str]:
    """Retourne une copie nettoyée d'une ligne CSV."""
    normalized = {key: normalize_text(value) for key, value in row.items()}

    if "booth_node_id" in normalized:
        normalized["booth_node_id"] = normalize_osm_id_list(
            normalized.get("booth_node_id", "")
        )
    if "booth_way_id" in normalized:
        normalized["booth_way_id"] = normalize_osm_id_list(
            normalized.get("booth_way_id", "")
        )
    if "lat" in normalized:
        normalized["lat"] = normalize_number(normalized.get("lat", ""))
    if "lon" in normalized:
        normalized["lon"] = normalize_number(normalized.get("lon", ""))
    if "nbs_booth" in normalized:
        normalized["nbs_booth"] = normalize_number(normalized.get("nbs_booth", ""))

    return normalized


def read_csv_rows(
    input_files: List[str], file_type: str
) -> Tuple[List[str], List[Dict[str, str]]]:
    """Lit plusieurs CSV homogènes et retourne leur en-tête et leurs lignes."""
    print(f"\n📋 Fusion de {len(input_files)} fichier(s) de type '{file_type}'...")

    all_rows: List[Dict[str, str]] = []
    header: Optional[List[str]] = None

    for file_path in input_files:
        if not Path(file_path).exists():
            print(f"  ⚠️  Fichier non trouvé: {file_path}")
            continue

        delimiter = detect_delimiter(file_path)

        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=delimiter)

            if header is None:
                header = reader.fieldnames or []

            if reader.fieldnames != header:
                print(f"  ⚠️  Attention: Headers différents dans {Path(file_path).name}")

            rows_read = 0
            for row in reader:
                all_rows.append(normalize_row(row))
                rows_read += 1

            print(f"  📄 Lecture: {Path(file_path).name}")
            print(f"    → {rows_read} ligne(s) lues")

    if header is None:
        header = []

    print(f"\n  Total avant dédoublonnage: {len(all_rows)} ligne(s)")
    return header, all_rows


def write_csv_rows(
    output_file: str, header: List[str], rows: List[Dict[str, str]], file_type: str
) -> int:
    """Écrit un CSV en conservant l'en-tête d'origine."""
    print(f"  Total après dédoublonnage: {len(rows)} ligne(s)")
    print(f"\n  💾 Écriture du fichier: {Path(output_file).name}")

    with open(output_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    print(f"    ✅ {len(rows)} ligne(s) écrite(s)")
    print(f"\n✅ Fusion terminée avec succès: {output_file}\n")
    return len(rows)


def ordered_unique(values: List[str]) -> List[str]:
    """Supprime les doublons tout en conservant l'ordre d'apparition."""
    seen = set()
    out = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def merge_distinct_field(values: List[str]) -> str:
    """Concatène des valeurs distinctes en conservant l'ordre."""
    distinct = ordered_unique(
        [normalize_text(value) for value in values if normalize_text(value)]
    )
    return " - ".join(distinct)


def choose_first_non_empty(rows: List[Dict[str, str]], field: str) -> str:
    """Retourne la première valeur non vide pour un champ donné."""
    for row in rows:
        value = normalize_text(row.get(field, ""))
        if value:
            return value
    return ""


def get_signature(row: Dict[str, str]) -> Optional[Tuple[str, str, str]]:
    """Construit une signature d'identité OSM à partir des IDs disponibles."""
    node_ids = row.get("booth_node_id", "")
    way_ids = row.get("booth_way_id", "")
    toll_type = row.get("type", "")

    if node_ids and node_ids != "[]":
        return ("node", node_ids, toll_type)
    if way_ids and way_ids != "[]":
        return ("way", way_ids, toll_type)
    return None


def collect_field_values(
    rows: List[Dict[str, str]], field: str
) -> Dict[str, List[str]]:
    """Retourne les valeurs non vides d'un champ indexées par leur forme normalisée."""
    values: Dict[str, List[str]] = {}
    for row in rows:
        raw = normalize_text(row.get(field, ""))
        if not raw:
            continue
        values.setdefault(raw, []).append(row.get("name", ""))
    return values


def find_alias_conflicts(rows: List[Dict[str, str]]) -> List[str]:
    """Retourne les incompatibilités bloquant une fusion par alias."""
    conflicts = []
    fields_to_check = ["lat", "lon", "nbs_booth", "type"]

    for field in fields_to_check:
        distinct_values = collect_field_values(rows, field)
        if len(distinct_values) <= 1:
            continue
        formatted = ", ".join(
            f"{value} ({', '.join(sorted(set(names)))})"
            for value, names in sorted(distinct_values.items())
        )
        conflicts.append(f"champ '{field}' incompatible: {formatted}")

    distinct_way_ids = collect_field_values(rows, "booth_way_id")
    if len(distinct_way_ids) > 1:
        formatted = ", ".join(
            f"{value} ({', '.join(sorted(set(names)))})"
            for value, names in sorted(distinct_way_ids.items())
        )
        conflicts.append(f"champ 'booth_way_id' incompatible: {formatted}")

    return conflicts


def merge_duplicate_name_row(
    existing: Dict[str, str], row: Dict[str, str]
) -> Tuple[Dict[str, str], List[str]]:
    """Fusionne deux lignes portant exactement le même nom."""
    merged = dict(existing)
    warnings = []
    name = existing.get("name", "")

    strict_fields = [
        "booth_node_id",
        "booth_way_id",
        "lat",
        "lon",
        "nbs_booth",
        "type",
        "osm_name",
    ]

    for field in strict_fields:
        existing_value = normalize_text(existing.get(field, ""))
        new_value = normalize_text(row.get(field, ""))

        if existing_value and new_value and existing_value != new_value:
            warnings.append(
                f"  ⚠️  Conflit pour '{name}' sur '{field}': {existing_value} vs {new_value}"
            )
            continue

        if not existing_value and new_value:
            merged[field] = new_value

    operator_refs = merge_distinct_field(
        [existing.get("operator_ref", ""), row.get("operator_ref", "")]
    )
    if operator_refs:
        merged["operator_ref"] = operator_refs

    return merged, warnings


def merge_toll_info_rows(
    rows: List[Dict[str, str]],
) -> Tuple[List[Dict[str, str]], Dict[str, str], List[str], List[str]]:
    """
    Fusionne toll_info en regroupant les alias qui partagent strictement les mêmes IDs OSM.

    Returns:
        merged_rows, alias_map, warnings, merged_groups
    """
    warnings: List[str] = []
    alias_map: Dict[str, str] = {}
    merged_groups: List[str] = []

    rows_by_name: Dict[str, Dict[str, str]] = {}
    ordered_names: List[str] = []

    for row in rows:
        name = normalize_text(row.get("name", ""))
        if not name:
            continue

        if name in rows_by_name:
            merged_row, row_warnings = merge_duplicate_name_row(rows_by_name[name], row)
            rows_by_name[name] = merged_row
            warnings.extend(row_warnings)
        else:
            rows_by_name[name] = dict(row)
            ordered_names.append(name)

    rows_after_exact_name_merge = [rows_by_name[name] for name in ordered_names]

    grouped_by_signature: Dict[Tuple[str, str, str], List[Dict[str, str]]] = {}
    rows_without_signature: List[Dict[str, str]] = []

    for row in rows_after_exact_name_merge:
        signature = get_signature(row)
        if signature is None:
            rows_without_signature.append(row)
            alias_map[row["name"]] = row["name"]
            continue

        grouped_by_signature.setdefault(signature, []).append(row)

    merged_rows: List[Dict[str, str]] = []

    for row in rows_without_signature:
        merged_rows.append(row)

    for grouped_rows in grouped_by_signature.values():
        if len(grouped_rows) == 1:
            row = grouped_rows[0]
            alias_map[row["name"]] = row["name"]
            merged_rows.append(row)
            continue

        conflicts = find_alias_conflicts(grouped_rows)
        if conflicts:
            names = ", ".join(row["name"] for row in grouped_rows)
            warnings.append(
                f"  ⚠️  Fusion alias ignorée pour [{names}] malgré IDs OSM communs: "
                + " | ".join(conflicts)
            )
            for row in grouped_rows:
                alias_map[row["name"]] = row["name"]
                merged_rows.append(row)
            continue

        ordered_names_in_group = ordered_unique([row["name"] for row in grouped_rows])
        merged_name = " - ".join(ordered_names_in_group)
        merged_row = dict(grouped_rows[0])
        merged_row["name"] = merged_name
        merged_row["osm_name"] = choose_first_non_empty(grouped_rows, "osm_name")
        merged_row["operator_ref"] = merge_distinct_field(
            [row.get("operator_ref", "") for row in grouped_rows]
        )
        merged_row["lat"] = choose_first_non_empty(grouped_rows, "lat")
        merged_row["lon"] = choose_first_non_empty(grouped_rows, "lon")
        merged_row["nbs_booth"] = choose_first_non_empty(grouped_rows, "nbs_booth")
        merged_row["booth_node_id"] = choose_first_non_empty(
            grouped_rows, "booth_node_id"
        )
        merged_row["booth_way_id"] = choose_first_non_empty(
            grouped_rows, "booth_way_id"
        )
        merged_row["type"] = choose_first_non_empty(grouped_rows, "type")
        merged_row["operator_osm"] = choose_first_non_empty(
            grouped_rows, "operator_osm"
        )

        for original_name in ordered_names_in_group:
            alias_map[original_name] = merged_name

        merged_rows.append(merged_row)
        merged_groups.append(merged_name)

    return merged_rows, alias_map, warnings, merged_groups


def apply_aliases_to_price_rows(
    rows: List[Dict[str, str]], file_type: str, alias_map: Dict[str, str]
) -> List[Dict[str, str]]:
    """Réécrit les noms des CSV de prix avec les alias fusionnés."""
    rewritten_rows = []
    for row in rows:
        new_row = dict(row)
        if file_type == "close":
            new_row["name_from"] = alias_map.get(
                new_row.get("name_from", ""), new_row.get("name_from", "")
            )
            new_row["name_to"] = alias_map.get(
                new_row.get("name_to", ""), new_row.get("name_to", "")
            )
        else:
            new_row["name"] = alias_map.get(
                new_row.get("name", ""), new_row.get("name", "")
            )
        rewritten_rows.append(new_row)
    return rewritten_rows


def deduplicate_price_rows(
    rows: List[Dict[str, str]], file_type: str
) -> List[Dict[str, str]]:
    """Dédoublonne les lignes de prix après réécriture des alias."""
    seen = set()
    unique_rows = []

    for row in rows:
        if file_type == "close":
            key = (row.get("name_from", ""), row.get("name_to", ""))
        else:
            key = row.get("name", "")

        if key in seen:
            continue

        seen.add(key)
        unique_rows.append(row)

    return unique_rows


def main():
    """Point d'entrée principal du script."""
    parser = argparse.ArgumentParser(
        description="Fusion globale des triplets ASF, AREA, APRR et COFIROUTE."
    )
    parser.add_argument(
        "--recompile",
        action="store_true",
        help="Ré-exécute les scripts de parsing de chaque opérateur avant la fusion.",
    )
    args = parser.parse_args()

    # Répertoire de base
    base_dir = Path(__file__).parent

    # Recompilation si demandée
    if args.recompile:
        recompile_operators(base_dir)

    print("=" * 80)
    print("🚀 FUSION GLOBALE DES TRIPLETS ASF, AREA, APRR ET COFIROUTE")
    print("=" * 80)

    # Chemins des fichiers sources
    asf_close = base_dir / "ASF" / "ASF_data_price_close_2025.csv"
    asf_open = base_dir / "ASF" / "ASF_data_price_open_2025.csv"
    asf_toll_info = base_dir / "ASF" / "ASF_toll_info.csv"

    area_close = base_dir / "AREA" / "AREA_data_price_close.csv"
    area_open = base_dir / "AREA" / "AREA_data_price_open.csv"
    area_toll_info = base_dir / "AREA" / "AREA_toll_info.csv"

    aprr_close = base_dir / "APRR" / "APRR_data_price_close_2026.csv"
    aprr_open = base_dir / "APRR" / "APRR_data_price_open_2026.csv"
    aprr_toll_info = base_dir / "APRR" / "APRR_toll_info.csv"

    cofiroute_close = (
        base_dir / "COFIROUTE" / "all" / "COFIROUTE_data_price_close_2026.csv"
    )
    cofiroute_open = (
        base_dir / "COFIROUTE" / "all" / "COFIROUTE_data_price_open_2026.csv"
    )
    cofiroute_toll_info = (
        base_dir / "COFIROUTE" / "all" / "COFIROUTE_toll_info_2026.csv"
    )

    # Vérification de l'existence des fichiers
    print("\n📁 Vérification des fichiers sources...")
    all_files_exist = True

    for file_path in [
        asf_close,
        asf_open,
        asf_toll_info,
        area_close,
        area_open,
        area_toll_info,
        aprr_close,
        aprr_open,
        aprr_toll_info,
        cofiroute_close,
        cofiroute_open,
        cofiroute_toll_info,
    ]:
        if file_path.exists():
            print(f"  ✅ {file_path.relative_to(base_dir)}")
        else:
            print(f"  ❌ MANQUANT: {file_path.relative_to(base_dir)}")
            all_files_exist = False

    if not all_files_exist:
        print("\n❌ ERREUR: Certains fichiers sources sont manquants!")
        sys.exit(1)

    # Chemins des fichiers de sortie
    output_close = base_dir / "GLOBAL_data_price_close.csv"
    output_open = base_dir / "GLOBAL_data_price_open.csv"
    output_toll_info = base_dir / "GLOBAL_toll_info.csv"

    close_inputs = [
        str(asf_close),
        str(area_close),
        str(aprr_close),
        str(cofiroute_close),
    ]
    open_inputs = [str(asf_open), str(area_open), str(aprr_open), str(cofiroute_open)]
    toll_info_inputs = [
        str(asf_toll_info),
        str(area_toll_info),
        str(aprr_toll_info),
        str(cofiroute_toll_info),
    ]

    print("\n" + "=" * 80)
    print("  ÉTAPE 1/4: Lecture des fichiers sources")
    print("=" * 80)

    close_header, close_rows = read_csv_rows(close_inputs, "close")
    open_header, open_rows = read_csv_rows(open_inputs, "open")
    toll_info_header, toll_info_rows = read_csv_rows(toll_info_inputs, "toll_info")

    print("\n" + "=" * 80)
    print("  ÉTAPE 2/4: Fusion intelligente du Toll Info")
    print("=" * 80)

    merged_toll_info_rows, alias_map, toll_info_warnings, merged_alias_groups = (
        merge_toll_info_rows(toll_info_rows)
    )

    for warning in toll_info_warnings:
        print(warning)

    if merged_alias_groups:
        print(
            f"  🔗 {len(merged_alias_groups)} groupe(s) d'alias fusionné(s) sur IDs OSM identiques"
        )
        for merged_name in merged_alias_groups:
            print(f"    - {merged_name}")
    else:
        print("  ℹ️  Aucun alias supplémentaire à fusionner")

    toll_info_count = write_csv_rows(
        str(output_toll_info), toll_info_header, merged_toll_info_rows, "toll_info"
    )

    print("=" * 80)
    print("  ÉTAPE 3/4: Réécriture et fusion des fichiers Close/Open")
    print("=" * 80)

    rewritten_close_rows = apply_aliases_to_price_rows(close_rows, "close", alias_map)
    rewritten_open_rows = apply_aliases_to_price_rows(open_rows, "open", alias_map)

    close_count = write_csv_rows(
        str(output_close),
        close_header,
        deduplicate_price_rows(rewritten_close_rows, "close"),
        "close",
    )

    open_count = write_csv_rows(
        str(output_open),
        open_header,
        deduplicate_price_rows(rewritten_open_rows, "open"),
        "open",
    )

    print("=" * 80)
    print("  ÉTAPE 4/4: Résumé")
    print("=" * 80)

    # Résumé final
    print("=" * 80)
    print("  📊 RÉSUMÉ DES FICHIERS GÉNÉRÉS")
    print("=" * 80)
    print()
    print(f"{'Type':<15} {'Fichier':<40} {'Lignes':>10}")
    print("-" * 15 + " " + "-" * 40 + " " + "-" * 10)
    print(f"{'Prix Close':<15} {'GLOBAL_data_price_close.csv':<40} {close_count:>10}")
    print(f"{'Prix Open':<15} {'GLOBAL_data_price_open.csv':<40} {open_count:>10}")
    print(f"{'Toll Info':<15} {'GLOBAL_toll_info.csv':<40} {toll_info_count:>10}")
    print("-" * 15 + " " + "-" * 40 + " " + "-" * 10)
    print(f"{'TOTAL':<15} {'':<40} {close_count + open_count + toll_info_count:>10}")
    print()
    print(f"📁 Tous les fichiers sont dans: {base_dir}")
    print()
    print("=" * 80)
    print()
    print("=" * 80)
    print("✅ FUSION GLOBALE TERMINÉE AVEC SUCCÈS!")
    print("=" * 80)


if __name__ == "__main__":
    main()
