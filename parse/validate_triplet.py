#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2025-2026 Louis TRIOULEYRE-ROBERJOT
# This file is part of TollData - Open French Highway Toll Database
"""
Script de validation de cohérence pour les triplets de fichiers CSV ASF.

Ce script vérifie que les trois fichiers (close, open, toll_info) sont cohérents:
- Tous les noms dans les fichiers de prix (close et open) doivent exister dans toll_info
- Tous les noms dans toll_info doivent être utilisés dans au moins un fichier de prix

Utilisation:
    python validate_triplet.py <close_csv> <open_csv> <toll_info_csv>
"""

import csv
import sys
from pathlib import Path
from typing import Set, Tuple


class TripletValidationError(Exception):
    """Exception levée lors d'erreurs de validation du triplet."""

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
            return ";"


def extract_names_from_close(file_path: str) -> Set[str]:
    """
    Extrait tous les noms de stations du fichier close (name_from et name_to).

    Args:
        file_path: Chemin du fichier CSV close

    Returns:
        Ensemble des noms de stations
    """
    names = set()

    if not Path(file_path).exists():
        return names  # Fichier n'existe pas, retourner ensemble vide

    delimiter = detect_delimiter(file_path)

    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=delimiter)

        for row in reader:
            name_from = row.get("name_from", "").strip()
            name_to = row.get("name_to", "").strip()

            if name_from:
                names.add(name_from)
            if name_to:
                names.add(name_to)

    return names


def extract_names_from_open(file_path: str) -> Set[str]:
    """
    Extrait tous les noms de stations du fichier open.

    Args:
        file_path: Chemin du fichier CSV open

    Returns:
        Ensemble des noms de stations
    """
    names = set()

    if not Path(file_path).exists():
        return names  # Fichier n'existe pas, retourner ensemble vide

    delimiter = detect_delimiter(file_path)

    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=delimiter)

        for row in reader:
            name = row.get("name", "").strip()

            if name:
                names.add(name)

    return names


def extract_names_from_toll_info(file_path: str) -> Set[str]:
    """
    Extrait tous les noms de stations du fichier toll_info.

    Args:
        file_path: Chemin du fichier CSV toll_info

    Returns:
        Ensemble des noms de stations
    """
    names = set()

    if not Path(file_path).exists():
        raise FileNotFoundError(f"Fichier toll_info introuvable: {file_path}")

    delimiter = detect_delimiter(file_path)

    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=delimiter)

        for row in reader:
            name = row.get("name", "").strip()

            if name:
                names.add(name)

    return names


def validate_triplet(close_csv: str, open_csv: str, toll_info_csv: str) -> bool:
    """
    Valide la cohérence entre les trois fichiers CSV.

    Args:
        close_csv: Chemin du fichier CSV des prix close
        open_csv: Chemin du fichier CSV des prix open
        toll_info_csv: Chemin du fichier CSV toll_info

    Returns:
        True si la validation réussit

    Raises:
        TripletValidationError: Si des incohérences sont détectées
        FileNotFoundError: Si le fichier toll_info n'existe pas
    """
    print("\n🔍 Validation de la cohérence du triplet CSV...")

    # Extraire les noms de chaque fichier
    print(f"  📄 Extraction des noms depuis {Path(close_csv).name}...")
    names_close = extract_names_from_close(close_csv)
    print(f"    → {len(names_close)} station(s) unique(s) trouvée(s)")

    print(f"  📄 Extraction des noms depuis {Path(open_csv).name}...")
    names_open = extract_names_from_open(open_csv)
    print(f"    → {len(names_open)} station(s) unique(s) trouvée(s)")

    print(f"  📄 Extraction des noms depuis {Path(toll_info_csv).name}...")
    names_toll_info = extract_names_from_toll_info(toll_info_csv)
    print(f"    → {len(names_toll_info)} station(s) unique(s) trouvée(s)")

    # Combiner tous les noms des fichiers de prix
    names_in_prices = names_close | names_open
    print(f"\n  Total de stations dans les fichiers de prix: {len(names_in_prices)}")

    # Vérification 1: Tous les noms dans les prix doivent être dans toll_info
    missing_in_toll_info = names_in_prices - names_toll_info

    # Vérification 2: Tous les noms dans toll_info doivent être dans au moins un fichier de prix
    missing_in_prices = names_toll_info - names_in_prices

    # Construire le message d'erreur si des incohérences sont détectées
    errors = []

    if missing_in_toll_info:
        error_msg = (
            f"\n  ❌ {len(missing_in_toll_info)} station(s) présente(s) dans les fichiers de prix "
            f"mais ABSENTE(S) de toll_info:\n"
        )
        for name in sorted(missing_in_toll_info):
            in_close = "close" if name in names_close else ""
            in_open = "open" if name in names_open else ""
            source = f"[{', '.join(filter(None, [in_close, in_open]))}]"
            error_msg += f"    - {name} {source}\n"
        errors.append(error_msg)

    if missing_in_prices:
        # Warning seulement - certaines stations peuvent exister sans prix
        warning_msg = (
            f"\n  ⚠️  {len(missing_in_prices)} station(s) présente(s) dans toll_info "
            f"mais ABSENTE(S) des fichiers de prix (normal si pas de données de prix):\n"
        )
        for name in sorted(missing_in_prices):
            warning_msg += f"    - {name}\n"
        print(warning_msg)

    if errors:
        full_error_msg = (
            "\n" + "=" * 80 + "\n❌ ERREUR DE VALIDATION DU TRIPLET\n" + "=" * 80
        )
        full_error_msg += "".join(errors)
        full_error_msg += (
            "\n" + "=" * 80 + "\n"
            "🔧 SOLUTION:\n"
            "  - Vérifiez que tous les noms dans les prix existent dans toll_info\n"
            "  - Vérifiez que tous les noms dans toll_info sont utilisés dans au moins un fichier de prix\n"
            "  - Assurez-vous que les noms sont normalisés de manière cohérente\n"
            + "="
            * 80
        )
        raise TripletValidationError(full_error_msg)

    # Validation réussie
    print("\n  ✅ Validation réussie:")
    print(f"    • Toutes les stations dans les prix existent dans toll_info")
    if missing_in_prices:
        print(
            f"    • {len(names_toll_info)} station(s) dans toll_info ({len(names_in_prices)} utilisées, {len(missing_in_prices)} sans prix)"
        )
    else:
        print(f"    • Toutes les stations dans toll_info sont utilisées dans les prix")
    print(f"    • {len(names_toll_info)} station(s) unique(s) validée(s)")

    return True


def main():
    """Point d'entrée principal du script."""
    if len(sys.argv) != 4:
        print(
            "Usage: python validate_triplet.py <close_csv> <open_csv> <toll_info_csv>"
        )
        print("\n  close_csv: Fichier CSV des prix close (name_from, name_to, ...)")
        print("  open_csv: Fichier CSV des prix open (name, ...)")
        print(
            "  toll_info_csv: Fichier CSV des informations de péages (name, osm_name, ...)"
        )
        sys.exit(1)

    close_csv = sys.argv[1]
    open_csv = sys.argv[2]
    toll_info_csv = sys.argv[3]

    try:
        validate_triplet(close_csv, open_csv, toll_info_csv)
        print("\n✅ Validation du triplet terminée avec succès!\n")
    except (TripletValidationError, FileNotFoundError) as e:
        print(f"\n{e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERREUR INATTENDUE: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
