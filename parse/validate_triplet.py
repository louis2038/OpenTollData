#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2025-2026 Louis TRIOULEYRE-ROBERJOT
# This file is part of TollData - Open French Highway Toll Database
"""
Single source of truth for triplet validation.

This module validates the consistency of a triplet of CSV files
(close, open, toll_info) used in the TollData pipeline. All validation
rules live here so that adding or modifying a check requires editing
only this file.

Checks performed
────────────────
1. File existence (toll_info required, close/open optional but warned).
2. CSV structure: required columns are present.
3. Numeric parsing: distances and prices are valid numbers.
4. Name consistency:
   a. Every name in price files exists in toll_info.
   b. Every name in toll_info appears in at least one price file (warning).
 5. Type coherence:
     a. Stations in the close file must have type='close' in toll_info.
     b. Stations in the open file must have type='open' in toll_info.
  6. GPS uniqueness: every (lat, lon) pair in toll_info must be unique.
  7. Booth node ID uniqueness: a booth_node_id must not be shared by 2 stations.

Usage (CLI):
    python validate_triplet.py <close_csv> <open_csv> <toll_info_csv>

Usage (import):
    from validate_triplet import validate_triplet, TripletValidationError

    try:
        validate_triplet(close_csv, open_csv, toll_info_csv)
    except TripletValidationError as e:
        ...
"""

import csv
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


# ───────────────────────────────────────────────────────────────────
# Exception
# ───────────────────────────────────────────────────────────────────


class TripletValidationError(Exception):
    """Raised when the triplet is inconsistent."""

    pass


# ───────────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────────


def detect_delimiter(file_path: str) -> str:
    """Auto-detect CSV delimiter (';' or ',')."""
    with open(file_path, "r", encoding="utf-8") as f:
        first_line = f.readline()
        if ";" in first_line:
            return ";"
        elif "," in first_line:
            return ","
        return ";"


def _to_float(value: str) -> Optional[float]:
    """Parse a numeric string accepting both '3.5' and '3,5'. Empty → None."""
    if value is None:
        return None
    s = value.strip() if isinstance(value, str) else str(value)
    if s == "":
        return None
    s = s.replace(",", ".")
    return float(s)


# ───────────────────────────────────────────────────────────────────
# CSV readers (validation-oriented)
# ───────────────────────────────────────────────────────────────────

CLOSE_REQUIRED_COLS = [
    "name_from",
    "name_to",
    "distance",
    "price1",
    "price2",
    "price3",
    "price4",
    "price5",
]
OPEN_REQUIRED_COLS = [
    "name",
    "distance",
    "price1",
    "price2",
    "price3",
    "price4",
    "price5",
]
TOLL_INFO_REQUIRED_COLS = [
    "name",
    "type",
    "booth_node_id",
]


def _read_and_validate_close(file_path: str) -> Tuple[Set[str], List[str]]:
    """
    Read the close CSV, validate structure and numeric values.

    Returns:
        (set of station names, list of error strings)
    """
    names: Set[str] = set()
    errors: List[str] = []
    fname = Path(file_path).name

    if not Path(file_path).exists():
        return names, errors  # absence handled elsewhere

    delimiter = detect_delimiter(file_path)

    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        missing_cols = [
            c for c in CLOSE_REQUIRED_COLS if c not in (reader.fieldnames or [])
        ]
        if missing_cols:
            errors.append(f"[{fname}] Colonnes manquantes: {missing_cols}")
            return names, errors

        for i, row in enumerate(reader, start=2):
            name_from = row.get("name_from", "").strip()
            name_to = row.get("name_to", "").strip()

            if not name_from or not name_to:
                errors.append(f"[{fname}] Ligne {i}: name_from ou name_to manquant.")
                continue

            names.add(name_from)
            names.add(name_to)

            # Numeric validation
            for col in ("distance", "price1", "price2", "price3", "price4", "price5"):
                try:
                    val = _to_float(row.get(col, ""))
                    if val is not None and (math.isnan(val) or math.isinf(val)):
                        errors.append(
                            f"[{fname}] Ligne {i}, colonne '{col}': valeur non-finie."
                        )
                except (ValueError, TypeError):
                    errors.append(
                        f"[{fname}] Ligne {i}, colonne '{col}': "
                        f"valeur non numérique '{row.get(col, '')}'."
                    )

    return names, errors


def _read_and_validate_open(file_path: str) -> Tuple[Set[str], List[str]]:
    """
    Read the open CSV, validate structure and numeric values.

    Returns:
        (set of station names, list of error strings)
    """
    names: Set[str] = set()
    errors: List[str] = []
    fname = Path(file_path).name

    if not Path(file_path).exists():
        return names, errors

    delimiter = detect_delimiter(file_path)

    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        missing_cols = [
            c for c in OPEN_REQUIRED_COLS if c not in (reader.fieldnames or [])
        ]
        if missing_cols:
            errors.append(f"[{fname}] Colonnes manquantes: {missing_cols}")
            return names, errors

        for i, row in enumerate(reader, start=2):
            name = row.get("name", "").strip()

            if not name:
                errors.append(f"[{fname}] Ligne {i}: name manquant.")
                continue

            names.add(name)

            for col in ("distance", "price1", "price2", "price3", "price4", "price5"):
                try:
                    val = _to_float(row.get(col, ""))
                    if val is not None and (math.isnan(val) or math.isinf(val)):
                        errors.append(
                            f"[{fname}] Ligne {i}, colonne '{col}': valeur non-finie."
                        )
                except (ValueError, TypeError):
                    errors.append(
                        f"[{fname}] Ligne {i}, colonne '{col}': "
                        f"valeur non numérique '{row.get(col, '')}'."
                    )

    return names, errors


def _read_toll_info(
    file_path: str,
) -> Tuple[
    Set[str],
    Dict[str, str],
    Dict[str, Tuple[str, str]],
    Dict[str, List[str]],
    List[str],
]:
    """
    Read toll_info CSV, extract names, types, coordinates and booth node IDs.

    Returns:
        (
            set of names,
            dict name→type,
            dict name→(lat, lon),
            dict name→list of booth node IDs,
            list of error strings,
        )
    """
    names: Set[str] = set()
    types: Dict[str, str] = {}
    coords: Dict[str, Tuple[str, str]] = {}
    booth_nodes: Dict[str, List[str]] = {}
    errors: List[str] = []
    fname = Path(file_path).name

    if not Path(file_path).exists():
        raise FileNotFoundError(f"Fichier toll_info introuvable: {file_path}")

    delimiter = detect_delimiter(file_path)

    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        missing_cols = [
            c for c in TOLL_INFO_REQUIRED_COLS if c not in (reader.fieldnames or [])
        ]
        if missing_cols:
            errors.append(f"[{fname}] Colonnes manquantes: {missing_cols}")
            return names, types, coords, booth_nodes, errors

        for i, row in enumerate(reader, start=2):
            name = row.get("name", "").strip()
            toll_type = row.get("type", "").strip()

            if not name:
                errors.append(f"[{fname}] Ligne {i}: name manquant.")
                continue

            if name in names:
                errors.append(f"[{fname}] Ligne {i}: nom en double '{name}'.")

            names.add(name)

            if toll_type not in ("close", "open"):
                errors.append(
                    f"[{fname}] Ligne {i}: type invalide '{toll_type}' "
                    f"pour '{name}' (attendu 'close' ou 'open')."
                )
            else:
                types[name] = toll_type

            # Extract coordinates
            lat = row.get("lat", "").strip()
            lon = row.get("lon", "").strip()
            if lat and lon:
                coords[name] = (lat, lon)

            # Extract booth node IDs
            booth_raw = row.get("booth_node_id", "")
            try:
                booth_ids = _parse_booth_node_ids(booth_raw)
            except ValueError as exc:
                errors.append(f"[{fname}] Ligne {i}, colonne 'booth_node_id': {exc}")
                booth_ids = []

            if len(booth_ids) != len(set(booth_ids)):
                errors.append(
                    f"[{fname}] Ligne {i}: doublon dans booth_node_id pour '{name}'."
                )

            booth_nodes[name] = booth_ids

    return names, types, coords, booth_nodes, errors


def _parse_booth_node_ids(value: str) -> List[str]:
    """Parse booth_node_id into a list of numeric node IDs."""
    if value is None:
        return []

    raw = value.strip() if isinstance(value, str) else str(value).strip()
    if raw == "":
        return []

    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if inner == "":
            return []
        parts = inner.split(",")
    else:
        parts = [raw]

    node_ids: List[str] = []
    for part in parts:
        node_id = part.strip().strip('"').strip("'")
        if not node_id:
            continue
        if not node_id.isdigit():
            raise ValueError(
                f"valeur non valide '{part.strip()}' (attendu une liste d'IDs numeriques)."
            )
        node_ids.append(node_id)

    return node_ids


# ───────────────────────────────────────────────────────────────────
# Main validation
# ───────────────────────────────────────────────────────────────────


def validate_triplet(
    close_csv: str,
    open_csv: str,
    toll_info_csv: str,
    *,
    verbose: bool = True,
) -> bool:
    """
    Validate consistency of a (close, open, toll_info) CSV triplet.

    Args:
        close_csv:     Path to the close price CSV.
        open_csv:      Path to the open price CSV.
        toll_info_csv: Path to the toll_info CSV.
        verbose:       If True, print progress/summary to stdout.

    Returns:
        True when validation passes.

    Raises:
        TripletValidationError: on any validation failure.
        FileNotFoundError:      if toll_info_csv does not exist.
    """

    def _log(msg: str) -> None:
        if verbose:
            print(msg)

    _log("\n  Validation de la cohérence du triplet CSV...")

    errors: List[str] = []
    warnings: List[str] = []

    # ── 1. Read & validate CSV structure ─────────────────────────

    _log(f"  Lecture de {Path(close_csv).name}...")
    names_close, close_errs = _read_and_validate_close(close_csv)
    errors.extend(close_errs)
    _log(f"    {len(names_close)} station(s) unique(s)")

    _log(f"  Lecture de {Path(open_csv).name}...")
    names_open, open_errs = _read_and_validate_open(open_csv)
    errors.extend(open_errs)
    _log(f"    {len(names_open)} station(s) unique(s)")

    _log(f"  Lecture de {Path(toll_info_csv).name}...")
    (
        names_toll_info,
        types_toll_info,
        coords_toll_info,
        booth_nodes_toll_info,
        info_errs,
    ) = _read_toll_info(toll_info_csv)
    errors.extend(info_errs)
    _log(f"    {len(names_toll_info)} station(s) unique(s)")

    names_in_prices = names_close | names_open
    _log(f"\n  Total stations dans les fichiers de prix: {len(names_in_prices)}")

    # ── 2. Name consistency ──────────────────────────────────────

    # 2a. Every price name must exist in toll_info
    missing_in_toll_info = names_in_prices - names_toll_info
    if missing_in_toll_info:
        for name in sorted(missing_in_toll_info):
            sources = []
            if name in names_close:
                sources.append("close")
            if name in names_open:
                sources.append("open")
            errors.append(
                f"Station '{name}' [{', '.join(sources)}] absente de toll_info."
            )

    # 2b. Every toll_info name should appear in prices (warning only)
    missing_in_prices = names_toll_info - names_in_prices
    if missing_in_prices:
        for name in sorted(missing_in_prices):
            warnings.append(
                f"Station '{name}' dans toll_info mais absente des fichiers de prix."
            )

    # ── 3. Type coherence ────────────────────────────────────────

    # 3a. Close stations must have type='close'
    for name in sorted(names_close):
        if name in types_toll_info and types_toll_info[name] != "close":
            errors.append(
                f"Station '{name}' est dans le fichier close "
                f"mais a type='{types_toll_info[name]}' dans toll_info."
            )

    # 3b. Open stations must have type='open'
    for name in sorted(names_open):
        if name in types_toll_info and types_toll_info[name] != "open":
            errors.append(
                f"Station '{name}' est dans le fichier open "
                f"mais a type='{types_toll_info[name]}' dans toll_info."
            )

    # ── 4. GPS coordinate uniqueness ─────────────────────────────

    coord_to_names: Dict[Tuple[str, str], List[str]] = {}
    for name, (lat, lon) in coords_toll_info.items():
        key = (lat, lon)
        coord_to_names.setdefault(key, []).append(name)

    for (lat, lon), station_names in sorted(coord_to_names.items()):
        if len(station_names) > 1:
            errors.append(
                f"Coordonnées GPS en double ({lat}, {lon}): "
                f"{', '.join(sorted(station_names))}"
            )

    # ── 5. Booth node ID uniqueness ───────────────────────────────

    booth_id_to_stations: Dict[str, Set[str]] = {}
    for station_name, booth_ids in booth_nodes_toll_info.items():
        for booth_id in booth_ids:
            booth_id_to_stations.setdefault(booth_id, set()).add(station_name)

    for booth_id, station_names in sorted(booth_id_to_stations.items()):
        if len(station_names) > 1:
            errors.append(
                f"booth_node_id en double ({booth_id}): "
                f"{', '.join(sorted(station_names))}"
            )

    # ── Report ───────────────────────────────────────────────────

    if warnings:
        _log(f"\n  {len(warnings)} avertissement(s):")
        for w in warnings:
            _log(f"    - {w}")

    if errors:
        report = (
            "\n" + "=" * 80 + "\n  ERREUR DE VALIDATION DU TRIPLET\n" + "=" * 80 + "\n"
        )
        for e in errors:
            report += f"  - {e}\n"
        report += (
            "\n" + "=" * 80 + "\n"
            "  SOLUTION:\n"
            "  - Verifiez que tous les noms dans les prix existent dans toll_info\n"
            "  - Verifiez que le type (open/close) dans toll_info correspond au fichier de prix utilise\n"
            "  - Assurez-vous que les valeurs numeriques sont correctes\n"
            "  - Assurez-vous qu'un booth_node_id n'est utilise que par une station\n"
            + "="
            * 80
        )
        raise TripletValidationError(report)

    # Success
    _log("\n  Validation reussie:")
    _log(f"    - Toutes les stations dans les prix existent dans toll_info")
    _log(f"    - Coherence des types (open/close) verifiee")
    _log(f"    - Coordonnees GPS uniques verifiees")
    _log(f"    - booth_node_id uniques verifies")
    if missing_in_prices:
        _log(
            f"    - {len(names_toll_info)} station(s) dans toll_info "
            f"({len(names_in_prices)} utilisees, {len(missing_in_prices)} sans prix)"
        )
    else:
        _log(f"    - Toutes les stations dans toll_info sont utilisees dans les prix")
    _log(f"    - {len(names_toll_info)} station(s) unique(s) validees")

    return True


# ───────────────────────────────────────────────────────────────────
# CLI
# ───────────────────────────────────────────────────────────────────


def main():
    """Command-line entry point."""
    if len(sys.argv) != 4:
        print(
            "Usage: python validate_triplet.py <close_csv> <open_csv> <toll_info_csv>"
        )
        print("\n  close_csv:     Fichier CSV des prix close (name_from, name_to, ...)")
        print("  open_csv:      Fichier CSV des prix open (name, ...)")
        print("  toll_info_csv: Fichier CSV toll_info (name, osm_name, ...)")
        sys.exit(1)

    close_csv = sys.argv[1]
    open_csv = sys.argv[2]
    toll_info_csv = sys.argv[3]

    try:
        validate_triplet(close_csv, open_csv, toll_info_csv)
        print("\n  Validation du triplet terminee avec succes!\n")
    except TripletValidationError as e:
        print(f"\n{e}\n", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"\n  ERREUR: {e}\n", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
