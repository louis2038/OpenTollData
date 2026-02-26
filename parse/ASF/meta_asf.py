#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2025-2026 Louis TRIOULEYRE-ROBERJOT
# This file is part of TollData - Open French Highway Toll Database
"""
Meta-script principal pour le traitement complet des données ASF.

Ce script orchestre l'ensemble du workflow de traitement des données:
1. Exécution de tous les scripts de parsing (page*/raw_data/parse_asf_*.py)
2. Consolidation par page: fusion des asf_*.csv en ASF_page*_*.csv
3. Validation du triplet par page
4. Fusion finale: fusion des ASF_page*_*.csv en ASF_*.csv
5. Validation du triplet final

Résultats par page:
- page*/ASF_page*_data_price_close_2025.csv
- page*/ASF_page*_data_price_open_2025.csv
- page*/ASF_page*_toll_info.csv

Résultats finaux:
- ASF_data_price_close_2025.csv
- ASF_data_price_open_2025.csv
- ASF_toll_info.csv

Auteur: OpenCode
Date: 2026-01-29
"""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List


class MetaScriptError(Exception):
    """Exception levée lors d'erreurs du meta-script."""

    pass


def run_command(script_path: Path, args: List[str] = None) -> None:
    """
    Exécute un script Python avec des arguments optionnels.

    Args:
        script_path: Chemin du script à exécuter
        args: Liste d'arguments à passer au script

    Raises:
        MetaScriptError: Si le script échoue
    """
    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)

    result = subprocess.run(cmd, cwd=script_path.parent)

    if result.returncode != 0:
        raise MetaScriptError(
            f"Le script {script_path.name} a échoué avec le code {result.returncode}"
        )


def find_csv_files(base_dir: Path, pattern: str) -> List[str]:
    """
    Trouve tous les fichiers CSV correspondant à un pattern.

    Args:
        base_dir: Répertoire de base
        pattern: Pattern de recherche (ex: "ASF_page*_data_price_close_2025.csv")

    Returns:
        Liste triée des chemins de fichiers trouvés
    """
    files = sorted(base_dir.glob(f"page*/{pattern}"))
    return [str(f) for f in files]


def find_page_directories(base_dir: Path) -> List[Path]:
    """
    Trouve tous les répertoires page*.

    Args:
        base_dir: Répertoire de base

    Returns:
        Liste triée des répertoires page*
    """
    return sorted([d for d in base_dir.glob("page*") if d.is_dir()])


def consolidate_page_csvs(page_dir: Path, merge_script: Path) -> None:
    """
    Consolide tous les fichiers CSV d'une page en créant le triplet ASF_page*_*.csv

    Args:
        page_dir: Répertoire de la page
        merge_script: Chemin du script merge_csv_files.py

    Raises:
        MetaScriptError: Si la fusion échoue
    """
    page_name = page_dir.name
    print(f"\n  📁 Consolidation de {page_name}...")

    # Chercher dans raw_data/ et à la racine de la page
    raw_data_dir = page_dir / "raw_data"
    search_dirs = [page_dir, raw_data_dir] if raw_data_dir.exists() else [page_dir]

    # Fusion des fichiers close
    close_pattern = "asf_prices_close_*.csv"
    close_files = []
    for search_dir in search_dirs:
        close_files.extend(sorted(search_dir.glob(close_pattern)))

    if close_files:
        output_close = page_dir / f"ASF_{page_name}_data_price_close_2025.csv"
        print(f"    🔹 Close: {len(close_files)} fichier(s) → {output_close.name}")
        args = ["close", str(output_close)] + [str(f) for f in close_files]
        run_command(merge_script, args)
    else:
        # Vérifier si le fichier consolidé existe déjà
        output_close = page_dir / f"ASF_{page_name}_data_price_close_2025.csv"
        if output_close.exists():
            print(f"    ✅ Close: fichier consolidé existant ({output_close.name})")
        else:
            print(f"    ⚠️  Aucun fichier close trouvé (pattern: {close_pattern})")

    # Fusion des fichiers open
    open_pattern = "asf_prices_open_*.csv"
    open_files = []
    for search_dir in search_dirs:
        open_files.extend(sorted(search_dir.glob(open_pattern)))

    if open_files:
        output_open = page_dir / f"ASF_{page_name}_data_price_open_2025.csv"
        print(f"    🔹 Open: {len(open_files)} fichier(s) → {output_open.name}")
        args = ["open", str(output_open)] + [str(f) for f in open_files]
        run_command(merge_script, args)
    else:
        # Vérifier si le fichier consolidé existe déjà
        output_open = page_dir / f"ASF_{page_name}_data_price_open_2025.csv"
        if output_open.exists():
            print(f"    ✅ Open: fichier consolidé existant ({output_open.name})")
        else:
            print(f"    ⚠️  Aucun fichier open trouvé (pattern: {open_pattern})")

    # Pour toll_info, on utilise directement le fichier ASF_page*_toll_info.csv s'il existe
    # Les fichiers asf_stations_*.csv sont des intermédiaires qui nécessitent un enrichissement manuel
    toll_info_file = page_dir / f"ASF_{page_name}_toll_info.csv"
    if toll_info_file.exists():
        print(f"    ✅ Toll Info: fichier existant ({toll_info_file.name})")
    else:
        print(f"    ⚠️  Aucun fichier toll_info trouvé ({toll_info_file.name})")

    print(f"    ✅ Consolidation de {page_name} terminée")


def print_banner(title: str) -> None:
    """Affiche une bannière de section."""
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}\n")


def print_summary(close_csv: Path, open_csv: Path, toll_info_csv: Path) -> None:
    """
    Affiche un résumé des fichiers générés.

    Args:
        close_csv: Chemin du fichier close
        open_csv: Chemin du fichier open
        toll_info_csv: Chemin du fichier toll_info
    """
    print_banner("📊 RÉSUMÉ DES FICHIERS GÉNÉRÉS")

    # Compter les lignes de chaque fichier
    files_info = []

    for file_path, file_type in [
        (close_csv, "Prix Close"),
        (open_csv, "Prix Open"),
        (toll_info_csv, "Toll Info"),
    ]:
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                line_count = sum(1 for _ in f) - 1  # -1 pour l'en-tête
            files_info.append((file_type, file_path.name, line_count))
        else:
            files_info.append((file_type, file_path.name, 0))

    # Afficher le tableau
    print(f"{'Type':<15} {'Fichier':<40} {'Lignes':>10}")
    print(f"{'-' * 15} {'-' * 40} {'-' * 10}")

    for file_type, filename, line_count in files_info:
        print(f"{file_type:<15} {filename:<40} {line_count:>10}")

    total_lines = sum(info[2] for info in files_info)
    print(f"{'-' * 15} {'-' * 40} {'-' * 10}")
    print(f"{'TOTAL':<15} {'':<40} {total_lines:>10}")

    print(f"\n📁 Tous les fichiers sont dans: {close_csv.parent}")
    print(f"\n{'=' * 80}\n")


def parse_arguments() -> argparse.Namespace:
    """Parse les arguments CLI du meta-script."""
    parser = argparse.ArgumentParser(
        description=(
            "Orchestre le traitement ASF complet. "
            "La fusion Toll Info est activée avec --newinfo."
        )
    )
    parser.add_argument(
        "--newinfo",
        action="store_true",
        help="Régénère et fusionne les fichiers Toll Info vers ASF_toll_info.csv",
    )
    return parser.parse_args()


def main():
    """Point d'entrée principal du meta-script."""
    cli_args = parse_arguments()
    regenerate_toll_info = cli_args.newinfo
    base_dir = Path(__file__).parent

    print("\n" + "=" * 80)
    print("🚀 META-SCRIPT ASF - TRAITEMENT COMPLET DES DONNÉES")
    print("=" * 80)
    print(f"\n📂 Répertoire de travail: {base_dir}")
    print(f"🎯 Objectif: Générer les triplets par page puis le triplet final ASF")
    print(
        f"🧾 Toll Info final: {'régénération activée (--newinfo)' if regenerate_toll_info else 'fichier existant conservé'}"
    )

    try:
        # ========================================
        # ÉTAPE 1: Exécuter tous les scripts de parsing
        # ========================================
        print_banner("ÉTAPE 1/6: Exécution des scripts de parsing")

        run_all_scripts_path = base_dir / "run_all_page_scripts.py"

        if run_all_scripts_path.exists():
            print("▶️  Exécution de run_all_page_scripts.py...")
            run_command(run_all_scripts_path)
        else:
            print(
                "⚠️  Script run_all_page_scripts.py non trouvé, passage à l'étape suivante"
            )

        # ========================================
        # ÉTAPE 2: Consolidation par page
        # ========================================
        print_banner("ÉTAPE 2/6: Consolidation des CSV par page")

        page_dirs = find_page_directories(base_dir)
        merge_script = base_dir / "../merge_csv_files.py"

        if not page_dirs:
            print("⚠️  Aucun répertoire page* trouvé")
        else:
            print(
                f"📋 {len(page_dirs)} page(s) trouvée(s): {', '.join(d.name for d in page_dirs)}"
            )

            for page_dir in page_dirs:
                consolidate_page_csvs(page_dir, merge_script)

        # ========================================
        # ÉTAPE 3: Validation des triplets par page
        # ========================================
        print_banner("ÉTAPE 3/6: Validation des triplets par page")

        validate_script = base_dir / "../validate_triplet.py"
        validated_pages = 0

        for page_dir in page_dirs:
            page_name = page_dir.name
            close_file = page_dir / f"ASF_{page_name}_data_price_close_2025.csv"
            open_file = page_dir / f"ASF_{page_name}_data_price_open_2025.csv"
            toll_info_file = page_dir / f"ASF_{page_name}_toll_info.csv"

            # Vérifier que le fichier toll_info existe (requis)
            if not toll_info_file.exists():
                print(f"  ⚠️  {page_name}: pas de toll_info, validation ignorée")
                continue

            # Créer des fichiers vides si close ou open n'existent pas
            if not close_file.exists():
                with open(close_file, "w", encoding="utf-8") as f:
                    f.write(
                        "name_from;name_to;distance;price1;price2;price3;price4;price5\n"
                    )

            if not open_file.exists():
                with open(open_file, "w", encoding="utf-8") as f:
                    f.write("name;distance;price1;price2;price3;price4;price5\n")

            print(f"  🔍 Validation de {page_name}...")
            args = [str(close_file), str(open_file), str(toll_info_file)]
            run_command(validate_script, args)
            validated_pages += 1

        print(f"\n  ✅ {validated_pages}/{len(page_dirs)} page(s) validée(s)")

        # ========================================
        # ÉTAPE 4: Fusion finale - Close
        # ========================================
        print_banner("ÉTAPE 4/6: Fusion finale des fichiers Close")

        close_files = find_csv_files(base_dir, "ASF_page*_data_price_close_2025.csv")
        output_close = base_dir / "ASF_data_price_close_2025.csv"

        if close_files:
            print(f"📋 {len(close_files)} fichier(s) trouvé(s)")
            args = ["close", str(output_close)] + close_files
            run_command(merge_script, args)
        else:
            print("⚠️  Aucun fichier close trouvé")
            with open(output_close, "w", encoding="utf-8") as f:
                f.write(
                    "name_from;name_to;distance;price1;price2;price3;price4;price5\n"
                )

        # ========================================
        # ÉTAPE 5: Fusion finale - Open
        # ========================================
        print_banner("ÉTAPE 5/6: Fusion finale des fichiers Open")

        open_files = find_csv_files(base_dir, "ASF_page*_data_price_open_2025.csv")
        output_open = base_dir / "ASF_data_price_open_2025.csv"

        if open_files:
            print(f"📋 {len(open_files)} fichier(s) trouvé(s)")
            args = ["open", str(output_open)] + open_files
            run_command(merge_script, args)
        else:
            print("⚠️  Aucun fichier open trouvé")
            with open(output_open, "w", encoding="utf-8") as f:
                f.write("name;distance;price1;price2;price3;price4;price5\n")

        # ========================================
        # ÉTAPE 6: Fusion finale - Toll Info + Validation finale
        # ========================================
        print_banner("ÉTAPE 6/6: Fusion finale Toll Info & Validation")

        output_toll_info = base_dir / "ASF_toll_info.csv"

        if regenerate_toll_info:
            toll_info_files = find_csv_files(base_dir, "ASF_page*_toll_info.csv")

            if toll_info_files:
                print(f"📋 {len(toll_info_files)} fichier(s) trouvé(s)")
                args = ["toll_info", str(output_toll_info)] + toll_info_files
                run_command(merge_script, args)
            else:
                raise MetaScriptError(
                    "❌ Aucun fichier toll_info trouvé! Au moins un fichier toll_info est requis avec --newinfo."
                )
        else:
            print("ℹ️  Fusion Toll Info ignorée (option --newinfo absente)")
            if not output_toll_info.exists():
                raise MetaScriptError(
                    "❌ ASF_toll_info.csv introuvable. Relancez avec --newinfo pour le générer."
                )

        # Validation du triplet final
        print("\n  🔍 Validation du triplet final...")
        args = [str(output_close), str(output_open), str(output_toll_info)]
        run_command(validate_script, args)

        # ========================================
        # RÉSUMÉ FINAL
        # ========================================
        print_summary(output_close, output_open, output_toll_info)

        print("=" * 80)
        print("✅ META-SCRIPT TERMINÉ AVEC SUCCÈS!")
        print("=" * 80)
        print("\n🎉 Tous les fichiers CSV consolidés ont été générés et validés!")
        print(f"\n📂 Fichiers finaux dans: {base_dir}")
        print(f"📂 Fichiers par page dans: {base_dir}/page*/\n")

    except MetaScriptError as e:
        print(f"\n❌ ERREUR: {e}\n")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Exécution interrompue par l'utilisateur\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERREUR INATTENDUE: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
