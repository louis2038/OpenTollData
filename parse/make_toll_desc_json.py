#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2025-2026 Louis TRIOULEYRE-ROBERJOT
# This file is part of TollData - Open French Highway Toll Database
"""
Create a description-only JSON file from a full toll network JSON.

This script removes the connection data and open toll price data,
keeping only the metadata and toll descriptions.

Usage:
    python make_toll_desc_json.py input.json output.json
    python make_toll_desc_json.py GLO_network_v1.json GLO_network_desc_v1.json
"""

import argparse
import json
import sys


def create_description_json(input_path, output_path):
    """
    Load a full toll network JSON and create a description-only version.

    Removes:
    - networks[*].connection (keeps only network_name and tolls)
    - open_toll_price
    """
    # Load input JSON
    print(f"📂 Chargement du fichier: {input_path}")
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ Fichier introuvable: {input_path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Erreur de parsing JSON: {e}", file=sys.stderr)
        sys.exit(1)

    # Create new structure with only description data
    desc_data = {
        "date": data.get("date", ""),
        "version": data.get("version", ""),
        "name": data.get("name", ""),
        "list_of_operator": data.get("list_of_operator", []),
        "list_of_toll": data.get("list_of_toll", []),
        "currency": data.get("currency", ""),
        "toll_description": data.get("toll_description", {}),
    }

    # Add networks without connections
    networks = data.get("networks", [])
    desc_networks = []
    for net in networks:
        desc_net = {
            "network_name": net.get("network_name", ""),
            "tolls": net.get("tolls", []),
        }
        desc_networks.append(desc_net)

    desc_data["networks"] = desc_networks

    # Write output JSON
    print(f"💾 Écriture du fichier: {output_path}")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(desc_data, f, ensure_ascii=False, indent=4)

    # Print summary
    print(f"✅ Fichier de description créé avec succès!")
    print(f"   - Nombre de péages: {len(desc_data.get('list_of_toll', []))}")
    print(f"   - Nombre de réseaux: {len(desc_networks)}")
    print(f"   - Nombre d'opérateurs: {len(desc_data.get('list_of_operator', []))}")

    # Size comparison
    import os

    input_size = os.path.getsize(input_path)
    output_size = os.path.getsize(output_path)
    reduction = (1 - output_size / input_size) * 100
    print(f"   - Taille originale: {input_size:,} octets")
    print(f"   - Taille réduite: {output_size:,} octets")
    print(f"   - Réduction: {reduction:.1f}%")


def main():
    parser = argparse.ArgumentParser(
        description="Créer un fichier JSON de description (sans connexions ni prix ouverts) à partir d'un fichier complet."
    )
    parser.add_argument(
        "input_file", help="Chemin vers le fichier JSON complet en entrée"
    )
    parser.add_argument(
        "output_file",
        nargs="?",
        help="Chemin vers le fichier JSON de description en sortie (optionnel, par défaut: ajoute '_desc' au nom)",
    )

    args = parser.parse_args()

    # If no output file specified, generate one from input name
    if args.output_file is None:
        import os

        base, ext = os.path.splitext(args.input_file)
        args.output_file = f"{base}_desc{ext}"

    create_description_json(args.input_file, args.output_file)


if __name__ == "__main__":
    main()
