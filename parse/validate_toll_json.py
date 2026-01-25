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


def _fmt_set(values, max_items=12):
    """Format a set/list for readable error messages."""

    values = sorted(str(v) for v in values)
    if len(values) <= max_items:
        return ", ".join(values)
    head = ", ".join(values[:max_items])
    return f"{head} (+{len(values) - max_items})"


def extra_validate(data):
    """Extra (cross-field) validation that JSON Schema can't express easily."""

    errors = []

    list_of_toll = data.get("list_of_toll", [])
    toll_set = set(list_of_toll) if isinstance(list_of_toll, list) else set()

    list_of_operator = data.get("list_of_operator", [])
    operator_set = (
        set(list_of_operator) if isinstance(list_of_operator, list) else set()
    )

    toll_description = data.get("toll_description", {})
    if not isinstance(toll_description, dict):
        errors.append("toll_description: must be an object")
        toll_description = {}

    # toll_description keys must match list_of_toll exactly
    td_keys = set(toll_description.keys())
    missing_td = toll_set - td_keys
    extra_td = td_keys - toll_set
    if missing_td:
        errors.append(
            f"toll_description: missing toll(s): {_fmt_set(missing_td)}"
        )
    if extra_td:
        errors.append(
            f"toll_description: unknown toll key(s): {_fmt_set(extra_td)}"
        )

    # operator must be in list_of_operator
    for toll_name, desc in toll_description.items():
        if not isinstance(desc, dict):
            errors.append(f"toll_description.{toll_name}: must be an object")
            continue
        operator = desc.get("operator")
        if operator is not None and operator not in operator_set:
            errors.append(
                f"toll_description.{toll_name}.operator: '{operator}' is not in list_of_operator"
            )

    # open/close classification derived from toll_description
    open_tolls = set()
    close_tolls = set()
    for toll_name, desc in toll_description.items():
        if not isinstance(desc, dict):
            continue
        t = desc.get("type")
        if t == "open":
            open_tolls.add(toll_name)
        elif t == "close":
            close_tolls.add(toll_name)

    # open_toll_price keys must match open tolls exactly
    open_toll_price = data.get("open_toll_price", {})
    if not isinstance(open_toll_price, dict):
        errors.append("open_toll_price: must be an object")
        open_toll_price = {}

    otp_keys = set(open_toll_price.keys())
    otp_unknown = otp_keys - toll_set
    if otp_unknown:
        errors.append(
            f"open_toll_price: unknown toll key(s): {_fmt_set(otp_unknown)}"
        )

    missing_otp = open_tolls - otp_keys
    extra_otp = otp_keys - open_tolls
    if missing_otp:
        errors.append(
            f"open_toll_price: missing price for open toll(s): {_fmt_set(missing_otp)}"
        )
    if extra_otp:
        errors.append(
            f"open_toll_price: contains non-open toll(s): {_fmt_set(extra_otp)}"
        )

    # networks + connections cross-checks
    networks = data.get("networks", [])
    if not isinstance(networks, list):
        errors.append("networks: must be an array")
        networks = []

    all_network_tolls = set()
    for idx, net in enumerate(networks):
        if not isinstance(net, dict):
            errors.append(f"networks[{idx}]: must be an object")
            continue

        net_tolls = net.get("tolls", [])
        if not isinstance(net_tolls, list):
            errors.append(f"networks[{idx}].tolls: must be an array")
            net_tolls = []

        net_toll_set = set(net_tolls)
        all_network_tolls |= net_toll_set

        unknown_net_tolls = net_toll_set - toll_set
        if unknown_net_tolls:
            errors.append(
                f"networks[{idx}].tolls: contains unknown toll(s): {_fmt_set(unknown_net_tolls)}"
            )

        # Only closed tolls should belong to closed networks
        non_close = sorted(
            [
                t
                for t in net_toll_set
                if isinstance(toll_description.get(t), dict)
                and toll_description[t].get("type") != "close"
            ]
        )
        if non_close:
            errors.append(
                f"networks[{idx}].tolls: contains non-close toll(s): {_fmt_set(non_close)}"
            )

        conn = net.get("connection", {})
        if not isinstance(conn, dict):
            errors.append(f"networks[{idx}].connection: must be an object")
            continue

        for src, dsts in conn.items():
            if src not in net_toll_set:
                errors.append(
                    f"networks[{idx}].connection: unknown source toll '{src}' (not in networks[{idx}].tolls)"
                )
                continue

            if not isinstance(dsts, dict):
                errors.append(
                    f"networks[{idx}].connection.{src}: must be an object"
                )
                continue

            for dst in dsts.keys():
                if dst not in net_toll_set:
                    errors.append(
                        f"networks[{idx}].connection.{src}: unknown destination toll '{dst}' (not in networks[{idx}].tolls)"
                    )

    # all close tolls must belong to some closed network
    missing_close_in_networks = close_tolls - all_network_tolls
    if missing_close_in_networks:
        errors.append(
            f"networks: missing close toll(s) in any network: {_fmt_set(missing_close_in_networks)}"
        )

    # open tolls should not appear in closed networks
    open_in_networks = open_tolls & all_network_tolls
    if open_in_networks:
        errors.append(
            f"networks: contains open toll(s): {_fmt_set(open_in_networks)}"
        )

    return errors


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
        extra_errors = extra_validate(data)
        if extra_errors:
            print(
                "❌ Erreur de validation (contraintes supplementaires):",
                file=sys.stderr,
            )
            for msg in extra_errors:
                print(f"   - {msg}", file=sys.stderr)
            return False

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
