#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to verify the JSON schema validation works correctly.

This script tests:
1. Valid JSON passes validation
2. Invalid JSON fails validation with appropriate error messages
3. Edge cases are handled properly
"""

import json
import sys
import tempfile
from pathlib import Path

try:
    import jsonschema
    from jsonschema import ValidationError, validate
except ImportError:
    print("❌ Module 'jsonschema' requis. Installez avec: pip install jsonschema")
    sys.exit(1)


def load_schema():
    """Load the toll network schema."""
    script_dir = Path(__file__).parent
    schema_path = script_dir / "toll_network_schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_valid_example():
    """Test that the example file is valid."""
    print("Test 1: Validation du fichier exemple...")
    script_dir = Path(__file__).parent
    example_path = script_dir / "example_toll_network.json"

    try:
        with open(example_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        schema = load_schema()
        validate(instance=data, schema=schema)
        print("  ✅ Fichier exemple valide")
        return True
    except ValidationError as e:
        print(f"  ❌ Fichier exemple invalide: {e.message}")
        return False
    except FileNotFoundError:
        print("  ⚠️  Fichier exemple non trouvé, test ignoré")
        return True


def test_invalid_date_format():
    """Test that invalid date format is rejected."""
    print("\nTest 2: Rejet de format de date invalide...")
    schema = load_schema()

    invalid_data = {
        "date": "2024-01-15",  # Wrong format, should be DD/MM/YYYY
        "version": "1.0",
        "name": "test",
        "list_of_operator": [],
        "list_of_toll": [],
        "currency": "EUR",
        "networks": [],
        "toll_description": {},
        "open_toll_price": {},
    }

    try:
        validate(instance=invalid_data, schema=schema)
        print("  ❌ Devrait rejeter le format de date invalide")
        return False
    except ValidationError:
        print("  ✅ Format de date invalide correctement rejeté")
        return True


def test_invalid_currency():
    """Test that invalid currency code is rejected."""
    print("\nTest 3: Rejet de code devise invalide...")
    schema = load_schema()

    invalid_data = {
        "date": "15/01/2024",
        "version": "1.0",
        "name": "test",
        "list_of_operator": [],
        "list_of_toll": [],
        "currency": "Euro",  # Should be 3-letter code
        "networks": [],
        "toll_description": {},
        "open_toll_price": {},
    }

    try:
        validate(instance=invalid_data, schema=schema)
        print("  ❌ Devrait rejeter le code devise invalide")
        return False
    except ValidationError:
        print("  ✅ Code devise invalide correctement rejeté")
        return True


def test_invalid_toll_type():
    """Test that invalid toll type is rejected."""
    print("\nTest 4: Rejet de type de péage invalide...")
    schema = load_schema()

    invalid_data = {
        "date": "15/01/2024",
        "version": "1.0",
        "name": "test",
        "list_of_operator": ["TestOp"],
        "list_of_toll": ["Toll1"],
        "currency": "EUR",
        "networks": [],
        "toll_description": {
            "Toll1": {
                "operator_ref": "A1",
                "lat": "48.8566",
                "lon": "2.3522",
                "operator": "TestOp",
                "type": "invalid_type",  # Should be 'open' or 'close'
                "node_id": [],
                "ways_id": [],
            }
        },
        "open_toll_price": {},
    }

    try:
        validate(instance=invalid_data, schema=schema)
        print("  ❌ Devrait rejeter le type de péage invalide")
        return False
    except ValidationError:
        print("  ✅ Type de péage invalide correctement rejeté")
        return True


def test_missing_price_class():
    """Test that missing price class is rejected."""
    print("\nTest 5: Rejet de classe de prix manquante...")
    schema = load_schema()

    invalid_data = {
        "date": "15/01/2024",
        "version": "1.0",
        "name": "test",
        "list_of_operator": ["TestOp"],
        "list_of_toll": ["Toll1"],
        "currency": "EUR",
        "networks": [],
        "toll_description": {
            "Toll1": {
                "operator_ref": "A1",
                "lat": "48.8566",
                "lon": "2.3522",
                "operator": "TestOp",
                "type": "open",
                "node_id": [],
                "ways_id": [],
            }
        },
        "open_toll_price": {
            "Toll1": {
                "distance": "10.5",
                "price": {
                    "class_1": "5.50",
                    "class_2": "8.25",
                    # Missing class_3, class_4, class_5
                },
            }
        },
    }

    try:
        validate(instance=invalid_data, schema=schema)
        print("  ❌ Devrait rejeter les classes de prix manquantes")
        return False
    except ValidationError:
        print("  ✅ Classes de prix manquantes correctement rejetées")
        return True


def test_valid_minimal_data():
    """Test that minimal valid data passes."""
    print("\nTest 6: Validation de données minimales valides...")
    schema = load_schema()

    valid_data = {
        "date": "15/01/2024",
        "version": "1.0",
        "name": "test",
        "list_of_operator": [],
        "list_of_toll": [],
        "currency": "EUR",
        "networks": [],
        "toll_description": {},
        "open_toll_price": {},
    }

    try:
        validate(instance=valid_data, schema=schema)
        print("  ✅ Données minimales valides acceptées")
        return True
    except ValidationError as e:
        print(f"  ❌ Données minimales devraient être valides: {e.message}")
        return False


def test_network_structure():
    """Test that network structure is validated correctly."""
    print("\nTest 7: Validation de la structure réseau...")
    schema = load_schema()

    valid_data = {
        "date": "15/01/2024",
        "version": "1.0",
        "name": "test",
        "list_of_operator": ["TestOp"],
        "list_of_toll": ["Toll1", "Toll2"],
        "currency": "EUR",
        "networks": [
            {
                "network_name": "component_1",
                "tolls": ["Toll1", "Toll2"],
                "connection": {
                    "Toll1": {
                        "Toll2": {
                            "distance": "100.5",
                            "price": {
                                "class_1": "10.50",
                                "class_2": "15.75",
                                "class_3": "21.00",
                                "class_4": "26.25",
                                "class_5": "31.50",
                            },
                        }
                    },
                    "Toll2": {},
                },
            }
        ],
        "toll_description": {
            "Toll1": {
                "operator_ref": "A1",
                "lat": "48.8566",
                "lon": "2.3522",
                "operator": "TestOp",
                "type": "close",
                "node_id": ["123"],
                "ways_id": ["456"],
            },
            "Toll2": {
                "operator_ref": "A2",
                "lat": "48.8577",
                "lon": "2.3533",
                "operator": "TestOp",
                "type": "close",
                "node_id": ["789"],
                "ways_id": [],
            },
        },
        "open_toll_price": {},
    }

    try:
        validate(instance=valid_data, schema=schema)
        print("  ✅ Structure réseau valide acceptée")
        return True
    except ValidationError as e:
        print(f"  ❌ Structure réseau devrait être valide: {e.message}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("Tests de validation du schéma JSON pour réseau de péage")
    print("=" * 60)

    tests = [
        test_valid_example,
        test_invalid_date_format,
        test_invalid_currency,
        test_invalid_toll_type,
        test_missing_price_class,
        test_valid_minimal_data,
        test_network_structure,
    ]

    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"  ❌ Erreur inattendue: {e}")
            results.append(False)

    # Summary
    print("\n" + "=" * 60)
    print("Résumé des tests")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Tests réussis: {passed}/{total}")

    if passed == total:
        print("✅ Tous les tests sont passés!")
        return 0
    else:
        print(f"❌ {total - passed} test(s) échoué(s)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
