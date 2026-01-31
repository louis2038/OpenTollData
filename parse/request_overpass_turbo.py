# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2025-2026 Louis TRIOULEYRE-ROBERJOT
# This file is part of TollData - Open French Highway Toll Database
import json
import time

import requests


def query_overpass(query: str, timeout: int = 180) -> dict:
    """
    Effectue une requête Overpass et retourne la réponse JSON

    Args:
        query: La requête Overpass au format string
        timeout: Timeout en secondes pour la requête

    Returns:
        dict: La réponse JSON parsée
    """
    overpass_url = "https://overpass-api.de/api/interpreter"

    try:
        response = requests.post(overpass_url, data={"data": query}, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Erreur lors de la requête Overpass: {e}")
    except json.JSONDecodeError as e:
        raise Exception(f"Erreur parsing Overpass JSON: {e}")


def save_json(data: dict, output_file: str):
    """Sauvegarde les données au format JSON"""
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Données sauvegardées dans: {output_file}")


def main():
    # Requête Overpass
    query = """
    [out:json][timeout:900][maxsize:1073741824];
    area["name"="Bretagne"]["admin_level"="4"]->.searchArea;
    (
      way["highway"~"^(motorway|motorway_link|trunk|trunk_link|primary|primary_link|secondary|secondary_link|tertiary|tertiary_link)$"](area.searchArea);
      node["barrier"="toll_booth"](area.searchArea);
    );
    out body;
    >;
    out skel qt;
    """

    """
    [out:json][timeout:180];
    area[name="France"][boundary=administrative][admin_level=2]->.searchArea;
    way["highway"~"^(motorway|motorway_link)$"]["operator"="AREA"](area.searchArea);
    out body;
    >;
    out skel qt;
    """

    """
    [out:json][timeout:180];
    area[name="France"][boundary=administrative][admin_level=2]->.searchArea;
    node["barrier"="toll_booth"]["operator"="AREA"](area.searchArea);
    out body;
    >;
    out skel qt;
    """

    print("Exécution de la requête Overpass...")

    try:
        # Effectuer la requête
        response_data = query_overpass(query)

        # Sauvegarder la réponse
        output_file = "overpass_network_bretagne.json"
        save_json(response_data, output_file)

        # Afficher quelques statistiques
        elements = response_data.get("elements", [])
        print(f"Nombre d'éléments récupérés: {len(elements)}")

    except Exception as e:
        print(f"Erreur: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
