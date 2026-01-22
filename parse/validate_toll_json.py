#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validate a toll network JSON file against the JSON Schema.

Usage:
    python validate_toll_json.py toll_network.json
    python validate_toll_json.py --schema custom_schema.json toll_network.json
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import jsonschema
    from jsonschema import SchemaError, ValidationError, validate
except ImportError:
    print("❌ Le module 'jsonschema' n'est pas installé.", file=sys.stderr)
    print("   Installez-le avec: pip install jsonschema", file=sys.stderr)
    sys.exit(1)


def load_json(path):
    """Load and parse a JSON file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Fichier introuvable: {path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Erreur de parsing JSON dans {path}:", file=sys.stderr)
        print(f"   {e}", file=sys.stderr)
        sys.exit(1)


def validate_toll_json(data_path, schema_path=None):
    """Validate toll network JSON against schema."""

    # Default schema path
    if schema_path is None:
        script_dir = Path(__file__).parent
        schema_path = script_dir / "toll_network_schema.json"

    # Load files
    print(f"📂 Chargement du fichier de données: {data_path}")
    data = load_json(data_path)

    print(f"📂 Chargement du schéma: {schema_path}")
    schema = load_json(schema_path)

    # Validate
    print("🔍 Validation en cours...")
    try:
        validate(instance=data, schema=schema)
        print("✅ Validation réussie! Le fichier JSON est conforme au schéma.")
        return True
    except SchemaError as e:
        print("❌ Erreur dans le schéma JSON:", file=sys.stderr)
        print(f"   {e.message}", file=sys.stderr)
        if e.path:
            print(f"   Chemin: {' -> '.join(str(p) for p in e.path)}", file=sys.stderr)
        return False
    except ValidationError as e:
        print("❌ Erreur de validation:", file=sys.stderr)
        print(f"   {e.message}", file=sys.stderr)
        if e.path:
            print(
                f"   Chemin dans le document: {' -> '.join(str(p) for p in e.path)}",
                file=sys.stderr,
            )
        if e.schema_path:
            print(
                f"   Règle du schéma: {' -> '.join(str(p) for p in e.schema_path)}",
                file=sys.stderr,
            )

        # Show the problematic value if available
        if e.instance is not None and not isinstance(e.instance, (dict, list)):
            print(f"   Valeur problématique: {e.instance}", file=sys.stderr)

        return False


def print_summary(data):
    """Print a summary of the toll network data."""
    print("\n📊 Résumé des données:")
    print(f"   - Date: {data.get('date', 'N/A')}")
    print(f"   - Version: {data.get('version', 'N/A')}")
    print(f"   - Nom: {data.get('name', 'N/A')}")
    print(f"   - Devise: {data.get('currency', 'N/A')}")
    print(f"   - Nombre de péages: {len(data.get('list_of_toll', []))}")
    print(f"   - Nombre d'opérateurs: {len(data.get('list_of_operator', []))}")
    print(f"   - Nombre de réseaux: {len(data.get('networks', []))}")
    print(f"   - Nombre de péages ouverts: {len(data.get('open_toll_price', {}))}")

    # Network details
    networks = data.get("networks", [])
    if networks:
        print("\n   Détails des réseaux:")
        for net in networks:
            network_name = net.get("network_name", "unknown")
            num_tolls = len(net.get("tolls", []))
            num_connections = sum(
                len(conns) for conns in net.get("connection", {}).values()
            )
            print(
                f"     • {network_name}: {num_tolls} péages, {num_connections} connexions"
            )


def main():
    parser = argparse.ArgumentParser(
        description="Valider un fichier JSON de réseau de péages contre le schéma JSON Schema."
    )
    parser.add_argument(
        "data_file", help="Chemin vers le fichier JSON de données à valider"
    )
    parser.add_argument(
        "--schema",
        "-s",
        help="Chemin vers le fichier JSON Schema (optionnel, utilise toll_network_schema.json par défaut)",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Afficher un résumé des données après validation",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Mode verbeux")

    args = parser.parse_args()

    # Validate
    is_valid = validate_toll_json(args.data_file, args.schema)

    # Print summary if requested and validation succeeded
    if is_valid and args.summary:
        data = load_json(args.data_file)
        print_summary(data)

    # Exit with appropriate code
    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()
