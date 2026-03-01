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
from typing import Set, Dict, List


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


def merge_csv_files(input_files: List[str], output_file: str, file_type: str) -> int:
    """
    Fusionne plusieurs fichiers CSV en un seul.

    Args:
        input_files: Liste des chemins des fichiers à fusionner
        output_file: Chemin du fichier de sortie
        file_type: Type de fichier ('close', 'open', ou 'toll_info')

    Returns:
        Nombre de lignes écrites (hors header)
    """
    print(f"\n📋 Fusion de {len(input_files)} fichier(s) de type '{file_type}'...")

    all_rows = []
    header = None

    # Lecture de tous les fichiers
    for file_path in input_files:
        if not Path(file_path).exists():
            print(f"  ⚠️  Fichier non trouvé: {file_path}")
            continue

        delimiter = detect_delimiter(file_path)

        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=delimiter)

            # Récupérer le header du premier fichier
            if header is None:
                header = reader.fieldnames

            # Vérifier la cohérence des headers
            if reader.fieldnames != header:
                print(f"  ⚠️  Attention: Headers différents dans {Path(file_path).name}")

            # Lire toutes les lignes
            rows_read = 0
            for row in reader:
                all_rows.append(row)
                rows_read += 1

            print(f"  📄 Lecture: {Path(file_path).name}")
            print(f"    → {rows_read} ligne(s) lues")

    if not all_rows:
        print("  ⚠️  Aucune donnée à écrire")
        return 0

    print(f"\n  Total avant dédoublonnage: {len(all_rows)} ligne(s)")

    # Dédoublonnage
    if file_type in ["close", "open"]:
        # Pour les fichiers de prix, on dédoublonne sur name_from/name_to ou name
        seen = set()
        unique_rows = []

        for row in all_rows:
            if file_type == "close":
                key = (row.get("name_from", ""), row.get("name_to", ""))
            else:  # open
                key = row.get("name", "")

            if key not in seen:
                seen.add(key)
                unique_rows.append(row)

        all_rows = unique_rows

    elif file_type == "toll_info":
        # Pour toll_info, on dédoublonne sur name et on vérifie la cohérence des OSM IDs
        name_to_row = {}

        for row in all_rows:
            name = row.get("name", "").strip()
            if not name:
                continue

            if name in name_to_row:
                # Vérifier la cohérence des IDs OSM
                existing = name_to_row[name]
                booth_node_id = normalize_osm_id_list(row.get("booth_node_id", ""))
                booth_way_id = normalize_osm_id_list(row.get("booth_way_id", ""))
                existing_node_id = normalize_osm_id_list(
                    existing.get("booth_node_id", "")
                )
                existing_way_id = normalize_osm_id_list(
                    existing.get("booth_way_id", "")
                )

                if booth_node_id and booth_node_id != existing_node_id:
                    print(
                        f"  ⚠️  Conflit OSM node_id pour '{name}': {existing_node_id} vs {booth_node_id}"
                    )

                if booth_way_id and booth_way_id != existing_way_id:
                    print(
                        f"  ⚠️  Conflit OSM way_id pour '{name}': {existing_way_id} vs {booth_way_id}"
                    )
            else:
                name_to_row[name] = row

        all_rows = list(name_to_row.values())

    print(f"  Total après dédoublonnage: {len(all_rows)} ligne(s)")

    # Écriture du fichier de sortie
    print(f"\n  💾 Écriture du fichier: {Path(output_file).name}")

    with open(output_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header, delimiter=";")
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"    ✅ {len(all_rows)} ligne(s) écrite(s)")
    print(f"\n✅ Fusion terminée avec succès: {output_file}\n")

    return len(all_rows)


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

    print("\n" + "=" * 80)
    print("  ÉTAPE 1/3: Fusion des fichiers Close")
    print("=" * 80)

    close_count = merge_csv_files(
        [
            str(asf_close),
            str(area_close),
            str(aprr_close),
            str(cofiroute_close),
        ],
        str(output_close),
        "close",
    )

    print("=" * 80)
    print("  ÉTAPE 2/3: Fusion des fichiers Open")
    print("=" * 80)

    open_count = merge_csv_files(
        [str(asf_open), str(area_open), str(aprr_open), str(cofiroute_open)],
        str(output_open),
        "open",
    )

    print("=" * 80)
    print("  ÉTAPE 3/3: Fusion des fichiers Toll Info")
    print("=" * 80)

    toll_info_count = merge_csv_files(
        [
            str(asf_toll_info),
            str(area_toll_info),
            str(aprr_toll_info),
            str(cofiroute_toll_info),
        ],
        str(output_toll_info),
        "toll_info",
    )

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
