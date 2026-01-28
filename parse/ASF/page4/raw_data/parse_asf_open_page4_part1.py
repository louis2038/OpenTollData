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

    with open(filepath, "r") as f:
        for line in f:
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

            matrix.append(row)

    # Trouver la longueur maximale
    max_len = max(len(row) for row in matrix)

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
    matrix_class1: np.ndarray,
    matrix_class2: np.ndarray,
    matrix_class3: np.ndarray,
    matrix_class4: np.ndarray,
    matrix_class5: np.ndarray,
    stations: list,
    output_filepath: str,
):
    """
    Génère un fichier CSV avec la structure name_from, name_to, price1
    Écrit une ligne pour chaque matrix[i,j] non-NaN (donc inclut les deux sens si présentes)
    """
    with open(output_filepath, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)  # delimiteur par défaut ','
        writer.writerow(
            [
                "name",
                "distance",
                "price1",
                "price2",
                "price3",
                "price4",
                "price5",
            ]
        )

        for station_idx, (i, j) in Opens:
            price1 = matrix_class1[i, j]
            price2 = matrix_class2[i, j]
            price3 = matrix_class3[i, j]
            price4 = matrix_class4[i, j]
            price5 = matrix_class5[i, j]

            writer.writerow(
                [
                    stations_all[station_idx],
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


if __name__ == "__main__":
    page = 4
    part = 1
    type = "open"
    date = 2025

    filepath_class1 = f"asf_data_page{page}_part{part}_class1_{date}.txt"
    filepath_class2 = f"asf_data_page{page}_part{part}_class2_{date}.txt"
    filepath_class3 = f"asf_data_page{page}_part{part}_class3_{date}.txt"
    filepath_class4 = f"asf_data_page{page}_part{part}_class4_{date}.txt"
    filepath_class5 = f"asf_data_page{page}_part{part}_class5_{date}.txt"

    names_filepath = f"asf_name_page{page}_part{part}_{date}.txt"

    output_csv = f"asf_prices_{type}_page{page}_part{part}.csv"
    output_stations_csv = f"asf_stations_{type}_page{page}_part{part}.csv"

    matrix_class1 = parse_asf_file(filepath_class1)
    matrix_class2 = parse_asf_file(filepath_class2)
    matrix_class3 = parse_asf_file(filepath_class3)
    matrix_class4 = parse_asf_file(filepath_class4)
    matrix_class5 = parse_asf_file(filepath_class5)

    stations_all = read_station_names(names_filepath)

    Opens = [(46, (45, 45)), (63, (63, 63))]

    generate_csv(
        matrix_class1,
        matrix_class2,
        matrix_class3,
        matrix_class4,
        matrix_class5,
        stations_all,
        output_csv,
    )

    stations_pruned = [stations_all[i] for i, _ in Opens]

    generate_stations_csv(stations_pruned, output_stations_csv)
