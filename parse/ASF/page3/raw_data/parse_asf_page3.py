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
        for i, station_from in enumerate(stations_all):
            for j, station_to in enumerate(stations_all):
                if i in desactivate_index or j in desactivate_index:
                    continue
                if j >= 1:
                    price1 = matrix_class1[j - 1, i]
                    price2 = matrix_class2[j - 1, i]
                    price3 = matrix_class3[j - 1, i]
                    price4 = matrix_class4[j - 1, i]
                    price5 = matrix_class5[j - 1, i]
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

                if i >= 1:
                    price1 = matrix_class1[i - 1, j]
                    price2 = matrix_class2[i - 1, j]
                    price3 = matrix_class3[i - 1, j]
                    price4 = matrix_class4[i - 1, j]
                    price5 = matrix_class5[i - 1, j]
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
    filepath_class1 = "asf_data_page3_class1_2025.txt"
    filepath_class2 = "asf_data_page3_class2_2025.txt"
    filepath_class3 = "asf_data_page3_class3_2025.txt"
    filepath_class4 = "asf_data_page3_class4_2025.txt"
    filepath_class5 = "asf_data_page3_class5_2025.txt"

    names_filepath = "asf_name_page3_2025.txt"
    output_csv = "asf_prices_page3.csv"
    output_stations_csv = "asf_stations_page3.csv"

    matrix_class1 = parse_asf_file(filepath_class1)
    matrix_class2 = parse_asf_file(filepath_class2)
    matrix_class3 = parse_asf_file(filepath_class3)
    matrix_class4 = parse_asf_file(filepath_class4)
    matrix_class5 = parse_asf_file(filepath_class5)

    stations_all = read_station_names(names_filepath)

    desactivate_index = [
        0,
        1,
        2,
        3,
        4,
        18,
        19,
        29,
        30,
        33,
        34,
        35,
        36,
        37,
        38,
        39,
        40,
        41,
        42,
    ]

    stations = []
    for i in range(len(stations_all)):
        if not i in desactivate_index:
            stations.append(stations_all[i])

    print(stations[:5])
    print(f"Dimensions de la matrice: {matrix_class1.shape}")
    print(f"Nombre de gares: {len(stations)}")
    print(f"Premières lignes:\n{matrix_class1[:5]}")
    print(f"Nombre de valeurs NaN: {np.sum(np.isnan(matrix_class1))}")

    generate_csv(
        matrix_class1,
        matrix_class2,
        matrix_class3,
        matrix_class4,
        matrix_class5,
        stations,
        output_csv,
    )
    generate_stations_csv(stations, output_stations_csv)
    print(f"Fichier CSV généré: {output_csv}")
    print(f"Fichier des stations généré: {output_stations_csv}")
