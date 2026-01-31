#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2025-2026 Louis TRIOULEYRE-ROBERJOT
# This file is part of TollData - Open French Highway Toll Database
"""
Script de fusion de fichiers CSV pour le projet ASF Toll Data.

Ce script fusionne plusieurs fichiers CSV du même type (close, open, ou toll_info)
en un seul fichier consolidé, avec validation des données.

Fonctionnalités:
- Détection automatique du délimiteur en entrée (';' ou ',')
- Sortie avec délimiteur ';' et encodage UTF-8
- Validation stricte pour toll_info: même name → mêmes IDs OSM
- Suppression des doublons exacts
- Gestion des champs optionnels (distance, operator_ref, operator_osm)
"""

import csv
import sys
from pathlib import Path
from typing import List, Dict, Set, Tuple


class CSVMergeError(Exception):
    """Exception levée lors d'erreurs de fusion CSV."""

    pass


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
            # Par défaut, on utilise ';'
            return ";"


def validate_toll_info_consistency(rows: List[Dict[str, str]]) -> None:
    """
    Valide la cohérence des données toll_info.

    Vérifie que pour un même name (clé primaire), les IDs OSM sont identiques.

    Args:
        rows: Liste des lignes du fichier toll_info

    Raises:
        CSVMergeError: Si des incohérences sont détectées
    """
    name_to_osm_data = {}

    for idx, row in enumerate(rows, start=2):  # start=2 car ligne 1 est l'en-tête
        name = row.get("name", "").strip()
        if not name:
            continue

        booth_node_id = row.get("booth_node_id", "").strip()
        booth_way_id = row.get("booth_way_id", "").strip()

        osm_key = (booth_node_id, booth_way_id)

        if name in name_to_osm_data:
            previous_osm_key, previous_line = name_to_osm_data[name]

            if osm_key != previous_osm_key:
                error_msg = (
                    f"\n❌ ERREUR: La station '{name}' a des IDs OSM différents:\n"
                    f"  - Ligne {previous_line}: booth_node_id='{previous_osm_key[0]}', "
                    f"booth_way_id='{previous_osm_key[1]}'\n"
                    f"  - Ligne {idx}: booth_node_id='{osm_key[0]}', "
                    f"booth_way_id='{osm_key[1]}'\n"
                    f"\nLa clé primaire 'name' doit avoir des IDs OSM cohérents."
                )
                raise CSVMergeError(error_msg)
        else:
            name_to_osm_data[name] = (osm_key, idx)


def read_csv_file(file_path: str) -> Tuple[List[str], List[Dict[str, str]]]:
    """
    Lit un fichier CSV et retourne les en-têtes et les lignes.

    Args:
        file_path: Chemin du fichier CSV

    Returns:
        Tuple (headers, rows) où headers est la liste des colonnes
        et rows est la liste des dictionnaires ligne
    """
    delimiter = detect_delimiter(file_path)

    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        headers = reader.fieldnames
        rows = list(reader)

    return headers, rows


def remove_duplicates(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Supprime les lignes dupliquées en conservant la première occurrence.

    Args:
        rows: Liste des lignes

    Returns:
        Liste des lignes sans doublons
    """
    seen = set()
    unique_rows = []

    for row in rows:
        # Convertir le dictionnaire en tuple trié pour pouvoir le hacher
        row_tuple = tuple(sorted(row.items()))

        if row_tuple not in seen:
            seen.add(row_tuple)
            unique_rows.append(row)

    return unique_rows


def merge_csv_files(input_files: List[str], output_file: str, csv_type: str) -> None:
    """
    Fusionne plusieurs fichiers CSV en un seul fichier consolidé.

    Args:
        input_files: Liste des chemins des fichiers CSV à fusionner
        output_file: Chemin du fichier CSV de sortie
        csv_type: Type de CSV - "close", "open", ou "toll_info"

    Raises:
        CSVMergeError: Si des erreurs de fusion ou validation sont détectées
        FileNotFoundError: Si un fichier d'entrée n'existe pas
    """
    if not input_files:
        raise CSVMergeError(f"Aucun fichier d'entrée fourni pour le type '{csv_type}'")

    # Vérifier que tous les fichiers existent
    for file_path in input_files:
        if not Path(file_path).exists():
            raise FileNotFoundError(f"Fichier introuvable: {file_path}")

    print(f"\n📋 Fusion de {len(input_files)} fichier(s) de type '{csv_type}'...")

    all_headers = None
    all_rows = []

    # Lire tous les fichiers
    for file_path in input_files:
        print(f"  📄 Lecture: {Path(file_path).name}")

        headers, rows = read_csv_file(file_path)

        # Vérifier la cohérence des en-têtes
        if all_headers is None:
            all_headers = headers
        elif headers != all_headers:
            raise CSVMergeError(
                f"Les en-têtes du fichier {file_path} ne correspondent pas:\n"
                f"  Attendu: {all_headers}\n"
                f"  Trouvé: {headers}"
            )

        all_rows.extend(rows)
        print(f"    → {len(rows)} ligne(s) lues")

    print(f"\n  Total avant dédoublonnage: {len(all_rows)} ligne(s)")

    # Supprimer les doublons
    all_rows = remove_duplicates(all_rows)
    print(f"  Total après dédoublonnage: {len(all_rows)} ligne(s)")

    # Validation spécifique pour toll_info
    if csv_type == "toll_info":
        print(f"\n  🔍 Validation de la cohérence des IDs OSM...")
        validate_toll_info_consistency(all_rows)
        print(f"    ✅ Validation réussie")

    # Écrire le fichier de sortie
    print(f"\n  💾 Écriture du fichier: {Path(output_file).name}")

    with open(output_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_headers, delimiter=";")
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"    ✅ {len(all_rows)} ligne(s) écrite(s)")
    print(f"\n✅ Fusion terminée avec succès: {output_file}")


def main():
    """Point d'entrée principal du script."""
    if len(sys.argv) < 4:
        print(
            "Usage: python merge_csv_files.py <csv_type> <output_file> <input_file1> [input_file2] ..."
        )
        print("  csv_type: 'close', 'open', ou 'toll_info'")
        print("  output_file: Chemin du fichier de sortie")
        print("  input_files: Liste des fichiers CSV à fusionner")
        sys.exit(1)

    csv_type = sys.argv[1]
    output_file = sys.argv[2]
    input_files = sys.argv[3:]

    if csv_type not in ["close", "open", "toll_info"]:
        print(
            f"❌ ERREUR: Type CSV invalide '{csv_type}'. Utilisez 'close', 'open', ou 'toll_info'."
        )
        sys.exit(1)

    try:
        merge_csv_files(input_files, output_file, csv_type)
    except (CSVMergeError, FileNotFoundError) as e:
        print(f"\n❌ ERREUR: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERREUR INATTENDUE: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
