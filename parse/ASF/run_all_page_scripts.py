#!/usr/bin/env python3
"""
Script d'exécution de tous les scripts de parsing ASF.

Ce script parcourt tous les répertoires page*/raw_data/ et exécute
tous les scripts parse_asf_*.py trouvés.

Fonctionnalités:
- Détection automatique de tous les scripts de parsing
- Exécution dans le bon répertoire de travail
- Capture et affichage des logs de chaque script
- Arrêt immédiat en cas d'erreur
"""

import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


class ScriptExecutionError(Exception):
    """Exception levée lors d'erreurs d'exécution de script."""

    pass


def find_parse_scripts(base_dir: Path) -> List[Tuple[Path, Path]]:
    """
    Trouve tous les scripts parse_asf_*.py dans les répertoires page*/raw_data/.

    Args:
        base_dir: Répertoire de base (parse/ASF/)

    Returns:
        Liste de tuples (script_path, working_directory)
    """
    scripts = []

    # Parcourir tous les répertoires page*
    for page_dir in sorted(base_dir.glob("page*")):
        if not page_dir.is_dir():
            continue

        raw_data_dir = page_dir / "raw_data"
        if not raw_data_dir.exists():
            continue

        # Trouver tous les scripts parse_asf_*.py
        for script_path in sorted(raw_data_dir.glob("parse_asf_*.py")):
            scripts.append((script_path, raw_data_dir))

    return scripts


def run_script(script_path: Path, working_dir: Path) -> None:
    """
    Exécute un script Python dans son répertoire de travail.

    Args:
        script_path: Chemin du script à exécuter
        working_dir: Répertoire de travail pour l'exécution

    Raises:
        ScriptExecutionError: Si le script échoue
    """
    print(f"\n{'=' * 80}")
    print(f"🔧 Exécution: {script_path.relative_to(working_dir.parent.parent)}")
    print(f"   Répertoire: {working_dir.relative_to(working_dir.parent.parent)}")
    print(f"{'=' * 80}\n")

    try:
        # Exécuter le script avec Python 3
        result = subprocess.run(
            [sys.executable, script_path.name],
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=300,  # Timeout de 5 minutes par script
        )

        # Afficher la sortie standard
        if result.stdout:
            print(result.stdout)

        # Vérifier le code de retour
        if result.returncode != 0:
            error_msg = f"\n❌ Le script a échoué avec le code {result.returncode}"

            if result.stderr:
                error_msg += f"\n\nErreur:\n{result.stderr}"

            raise ScriptExecutionError(error_msg)

        print(f"✅ Script exécuté avec succès: {script_path.name}\n")

    except subprocess.TimeoutExpired:
        raise ScriptExecutionError(
            f"❌ Le script a dépassé le délai d'exécution (5 minutes)"
        )
    except Exception as e:
        if isinstance(e, ScriptExecutionError):
            raise
        raise ScriptExecutionError(f"❌ Erreur lors de l'exécution: {e}")


def run_all_page_scripts(base_dir: Path = None) -> int:
    """
    Exécute tous les scripts de parsing trouvés dans les pages.

    Args:
        base_dir: Répertoire de base (parse/ASF/). Si None, utilise le répertoire du script.

    Returns:
        Nombre de scripts exécutés avec succès

    Raises:
        ScriptExecutionError: Si un script échoue
    """
    if base_dir is None:
        base_dir = Path(__file__).parent

    print("\n" + "=" * 80)
    print("🚀 EXÉCUTION DE TOUS LES SCRIPTS DE PARSING ASF")
    print("=" * 80)

    # Trouver tous les scripts
    print("\n🔍 Recherche des scripts de parsing...")
    scripts = find_parse_scripts(base_dir)

    if not scripts:
        print("⚠️  Aucun script de parsing trouvé dans les répertoires page*/raw_data/")
        return 0

    print(f"\n📋 {len(scripts)} script(s) trouvé(s):")
    for script_path, working_dir in scripts:
        rel_path = script_path.relative_to(base_dir)
        print(f"  • {rel_path}")

    # Exécuter tous les scripts
    print(f"\n{'=' * 80}")
    print("▶️  DÉBUT DE L'EXÉCUTION")
    print(f"{'=' * 80}")

    success_count = 0

    for idx, (script_path, working_dir) in enumerate(scripts, start=1):
        print(f"\n[{idx}/{len(scripts)}] ", end="")

        try:
            run_script(script_path, working_dir)
            success_count += 1
        except ScriptExecutionError as e:
            print(f"\n{e}\n")
            print(f"{'=' * 80}")
            print(
                f"❌ ÉCHEC: Arrêt de l'exécution après {success_count}/{len(scripts)} script(s) réussi(s)"
            )
            print(f"{'=' * 80}\n")
            raise

    # Résumé final
    print(f"\n{'=' * 80}")
    print("✅ TOUS LES SCRIPTS ONT ÉTÉ EXÉCUTÉS AVEC SUCCÈS")
    print(f"{'=' * 80}")
    print(f"\n📊 Résumé:")
    print(f"  • Scripts exécutés: {success_count}/{len(scripts)}")
    print(f"  • Taux de réussite: 100%")
    print(f"\n{'=' * 80}\n")

    return success_count


def main():
    """Point d'entrée principal du script."""
    try:
        # Déterminer le répertoire de base
        base_dir = Path(__file__).parent

        # Exécuter tous les scripts
        success_count = run_all_page_scripts(base_dir)

        if success_count == 0:
            sys.exit(0)

        sys.exit(0)

    except ScriptExecutionError:
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
