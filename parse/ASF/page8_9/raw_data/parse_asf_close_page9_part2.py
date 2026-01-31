# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2025-2026 Louis TRIOULEYRE-ROBERJOT
# This file is part of TollData - Open French Highway Toll Database
import csv
import re
import unicodedata

import numpy as np


def parse_asf_file(filepath: str) -> np.ndarray:
    """
    Parse le fichier ASF et retourne une matrice numpy.
    Les valeurs '.' sont remplacées par np.nan
    """
    matrix = []

    expected_len = None
    with open(filepath, "r") as f:
        for line_number, line in enumerate(f, start=1):
            # Remplacer les espaces multiples par un seul espace
            line_clean = re.sub(r"\s+", " ", line.strip())

            # print(f"cleaned line: '{line_clean}'")

            if not line_clean:
                continue

            # Split par espace
            values = line_clean.split(" ")

            # Convertir chaque valeur
            row = []
            for val in values:
                if val == ".":
                    row.append(np.nan)
                else:
                    # Remplacer virgule par point
                    row.append(float(val.replace(",", ".")))

            # print(f"parsed row: {row}")

            if expected_len is None:
                expected_len = len(row)
            elif len(row) != expected_len:
                raise ValueError(
                    f"Ligne {line_number} invalide dans {filepath}: "
                    f"{len(row)} colonnes (attendu {expected_len})."
                )

            matrix.append(row)

    if expected_len is None:
        raise ValueError(f"Fichier vide: {filepath}")

    # Trouver la longueur maximale
    max_len = expected_len

    # Padder avec NaN
    for row in matrix:
        while len(row) < max_len:
            row.append(np.nan)

    return np.array(matrix, dtype=float)


def read_station_names(filepath: str) -> list:
    """
    Lit et normalise les noms des gares depuis le fichier texte
    Normalisation : ASCII de base -> MAJUSCULE -> remplacer tout caractère qui n'est pas une lettre ou un chiffre par un espace
    """

    def normalize_name(s: str) -> str:
        if not s:
            return ""
        s = unicodedata.normalize("NFKC", s)
        s = "".join(
            c
            for c in unicodedata.normalize("NFD", s)
            if unicodedata.category(c) != "Mn"
        )
        s = re.sub(r"[^A-Za-z0-9]", " ", s)
        s = re.sub(r"\s+", " ", s)
        s = s.strip()
        return s.upper()

    stations = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            station_name = line.strip()
            if station_name:
                stations.append(normalize_name(station_name))
    return stations


def generate_csv(
    matrix_class1,
    matrix_class2,
    matrix_class3,
    matrix_class4,
    matrix_class5,
    stations_rows,
    stations_columns,
    output_filepath,
):
    """
    Génère un fichier CSV avec la structure name_from, name_to, price1
    Écrit une ligne pour chaque matrix[i,j] non-NaN (donc inclut les deux sens si présentes)
    """
    with open(output_filepath, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)  # delimiteur par défaut ','
        writer.writerow(
            [
                "name_from",
                "name_to",
                "distance",
                "price1",
                "price2",
                "price3",
                "price4",
                "price5",
            ]
        )

        rows, cols = matrix_class1.shape
        for i, station_from in enumerate(stations_rows):
            for j, station_to in enumerate(stations_columns):
                if i in desactivate_index_rows or j in desactivate_index_columns:
                    continue

                price1 = matrix_class1[i, j]
                price2 = matrix_class2[i, j]
                price3 = matrix_class3[i, j]
                price4 = matrix_class4[i, j]
                price5 = matrix_class5[i, j]
                if not np.isnan(price1):
                    writer.writerow(
                        [
                            station_from,
                            station_to,
                            None,
                            price1,
                            price2,
                            price3,
                            price4,
                            price5,
                        ]
                    )
                    writer.writerow(
                        [
                            station_to,
                            station_from,
                            None,
                            price1,
                            price2,
                            price3,
                            price4,
                            price5,
                        ]
                    )


def generate_stations_csv(stations: list, output_filepath: str):
    """
    Génère un CSV contenant uniquement les noms normalisés des stations (colonne 'name')
    """
    with open(output_filepath, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["name"])
        for s in stations:
            writer.writerow([s])


def assert_matrix_shape(matrix: np.ndarray, label: str, rows: int, cols: int):
    actual_rows, actual_cols = matrix.shape
    if actual_rows != rows or actual_cols != cols:
        raise ValueError(
            f"Matrice {label} invalide: {actual_rows}x{actual_cols} "
            f"(attendu {rows}x{cols})."
        )


if __name__ == "__main__":
    page = 9
    part = 2
    type = "close"
    date = 2025

    filepath_class1 = f"asf_data_page{page}_part{part}_class1_{date}.txt"
    filepath_class2 = f"asf_data_page{page}_part{part}_class2_{date}.txt"
    filepath_class3 = f"asf_data_page{page}_part{part}_class3_{date}.txt"
    filepath_class4 = f"asf_data_page{page}_part{part}_class4_{date}.txt"
    filepath_class5 = f"asf_data_page{page}_part{part}_class5_{date}.txt"

    output_csv = f"asf_prices_{type}_page{page}_part{part}.csv"
    output_stations_rows_csv = f"asf_stations_{type}_page{page}_part{part}_row.csv"
    output_stations_columns_csv = f"asf_stations_{type}_page{page}_part{part}_col.csv"
    output_stations_csv = f"asf_stations_{type}_page{page}_part{part}.csv"

    names_filepath_columns = f"asf_name_page{page}_part{part}_{date}_col.txt"
    names_filepath_rows = f"asf_name_page{page}_part{part}_{date}_row.txt"

    matrix_class1 = parse_asf_file(filepath_class1)
    matrix_class2 = parse_asf_file(filepath_class2)
    matrix_class3 = parse_asf_file(filepath_class3)
    matrix_class4 = parse_asf_file(filepath_class4)
    matrix_class5 = parse_asf_file(filepath_class5)

    stations_rows = read_station_names(names_filepath_rows)
    stations_columns = read_station_names(names_filepath_columns)

    desactivate_index_rows = [0]
    desactivate_index_columns = []

    print(f"Dimensions de la matrice: {matrix_class1.shape}")
    print(f"Nombre de gares rows: {len(stations_rows)}")
    print(f"Nombre de gares columns: {len(stations_columns)}")
    print(f"Premières lignes:\n{matrix_class1[:5]}")
    print(f"Nombre de valeurs NaN: {np.sum(np.isnan(matrix_class1))}")

    generate_csv(
        matrix_class1,
        matrix_class2,
        matrix_class3,
        matrix_class4,
        matrix_class5,
        stations_rows,
        stations_columns,
        output_csv,
    )

    stations_rows_small = []
    for i in range(len(stations_rows)):
        if not i in desactivate_index_rows:
            stations_rows_small.append(stations_rows[i])

    stations_columns_small = []
    for i in range(len(stations_columns)):
        if not i in desactivate_index_columns:
            stations_columns_small.append(stations_columns[i])

    generate_stations_csv(stations_rows_small, output_stations_rows_csv)
    generate_stations_csv(stations_columns_small, output_stations_columns_csv)
    print(f"Fichier CSV généré: {output_csv}")
    print(f"Fichier des stations généré: {output_stations_columns_csv}")
    print(f"Fichier des stations généré: {output_stations_rows_csv}")
