# Meta-Script ASF - Documentation

## Vue d'ensemble

Ce dossier contient un système automatisé pour traiter et consolider les données de tarifs autoroutiers ASF. Le système est composé de 4 scripts Python qui travaillent ensemble pour générer 3 fichiers CSV consolidés.

## Architecture

```
parse/ASF/
├── meta_asf.py                    # 🎯 Script orchestrateur principal
├── run_all_page_scripts.py        # 🔧 Exécuteur de tous les scripts de parsing
├── merge_csv_files.py             # 🔗 Fusion de fichiers CSV avec validation
├── validate_triplet.py            # ✅ Validation de cohérence du triplet
├── page1/, page2/, ... pageN/     # Dossiers de données par page
│   ├── raw_data/                  # Données brutes et scripts de parsing
│   │   └── parse_asf_*.py
│   ├── ASF_pageN_data_price_close_2025.csv
│   ├── ASF_pageN_data_price_open_2025.csv
│   └── ASF_pageN_toll_info.csv
├── ASF_data_price_close_2025.csv  # ✨ Résultat consolidé (close)
├── ASF_data_price_open_2025.csv   # ✨ Résultat consolidé (open)
└── ASF_toll_info.csv              # ✨ Résultat consolidé (toll info)
```

## Fichiers de Sortie

### 1. `ASF_data_price_close_2025.csv`
Prix des systèmes de péage fermés (entrée-sortie).
```
Format: name_from;name_to;distance;price1;price2;price3;price4;price5
```

### 2. `ASF_data_price_open_2025.csv`
Prix des systèmes de péage ouverts (tarif fixe).
```
Format: name;distance;price1;price2;price3;price4;price5
```

### 3. `ASF_toll_info.csv`
Informations sur les péages avec métadonnées OSM.
```
Format: name;osm_name;operator_ref;lat;lon;nbs_booth;booth_node_id;booth_way_id;type;operator_osm
```

**Note**: Les champs `distance`, `operator_ref`, et `operator_osm` sont optionnels.

## Utilisation

### Workflow Complet (Recommandé)

Pour exécuter l'ensemble du workflow (parsing + fusion + validation) :

```bash
cd parse/ASF
python3 meta_asf.py
```

**Ce script va :**
1. ✅ Exécuter tous les scripts de parsing dans `page*/raw_data/`
2. ✅ Fusionner tous les fichiers close
3. ✅ Fusionner tous les fichiers open
4. ✅ Fusionner tous les fichiers toll_info avec validation OSM
5. ✅ Valider la cohérence du triplet final

### Scripts Individuels

#### 1. Exécuter uniquement les scripts de parsing

```bash
python3 run_all_page_scripts.py
```

#### 2. Fusionner des fichiers CSV manuellement

```bash
# Fusion de fichiers close
python3 merge_csv_files.py close output.csv input1.csv input2.csv ...

# Fusion de fichiers open
python3 merge_csv_files.py open output.csv input1.csv input2.csv ...

# Fusion de fichiers toll_info (avec validation OSM)
python3 merge_csv_files.py toll_info output.csv input1.csv input2.csv ...
```

#### 3. Valider la cohérence d'un triplet

```bash
python3 validate_triplet.py close.csv open.csv toll_info.csv
```

## Fonctionnalités Clés

### 🔍 Détection Automatique du Délimiteur
Les scripts détectent automatiquement si les CSV d'entrée utilisent `;` ou `,` comme délimiteur.

### 🛡️ Validation Stricte
- **Toll Info**: Vérifie que le même `name` (clé primaire) a toujours les mêmes IDs OSM (`booth_node_id`, `booth_way_id`)
- **Triplet**: Vérifie que tous les noms dans les prix existent dans toll_info et vice-versa

### ⚠️ Gestion des Erreurs
Le meta-script s'arrête immédiatement en cas d'erreur et affiche un message détaillé.

### 🧹 Dédoublonnage Automatique
Les lignes dupliquées sont automatiquement supprimées lors de la fusion.

### 📊 Rapports Détaillés
Chaque étape affiche des statistiques claires sur le traitement.

## Format des Fichiers

### Encodage
Tous les fichiers de sortie sont encodés en **UTF-8**.

### Délimiteur
Tous les fichiers de sortie utilisent le délimiteur **`;`** (point-virgule).

### Normalisation des Noms
Les noms de stations doivent être normalisés avec la fonction suivante :

```python
import re
import unicodedata

def normalize_name(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )
    s = re.sub(r"[^A-Za-z0-9]", " ", s)
    s = re.sub(r"\s+", " ", s)
    s = s.strip()
    return s.upper()
```

**Le champ `name` est la clé primaire du système et doit être unique et cohérent.**

## Validation des Données

### Validation des IDs OSM (toll_info)

Le script `merge_csv_files.py` vérifie que pour un même `name`, les IDs OSM sont identiques :
- `booth_node_id` doit être identique
- `booth_way_id` doit être identique

**Exemple d'erreur :**
```
❌ ERREUR: La station 'PEAGE DE VIENNE' a des IDs OSM différents:
  - Ligne 5: booth_node_id='[123, 456]', booth_way_id='[]'
  - Ligne 12: booth_node_id='[123]', booth_way_id='[789]'
```

### Validation du Triplet

Le script `validate_triplet.py` vérifie :
1. Tous les noms dans `close` et `open` existent dans `toll_info`
2. Tous les noms dans `toll_info` sont utilisés dans au moins un fichier de prix

**Exemple d'erreur :**
```
❌ 5 station(s) présente(s) dans les fichiers de prix mais ABSENTE(S) de toll_info:
  - STATION_A [close]
  - STATION_B [open]
  ...
```

## Dépannage

### Problème : Délimiteurs mixtes dans un fichier

**Symptôme** : Le fichier a des `;` dans l'en-tête mais des `,` dans les données.

**Solution** : Corriger le script de parsing qui génère ce fichier pour utiliser un délimiteur cohérent.

### Problème : Station dans les prix mais pas dans toll_info

**Symptôme** : La validation échoue avec des noms manquants.

**Solutions possibles** :
1. Vérifier que le nom est normalisé de la même façon
2. Ajouter la station manquante dans le fichier toll_info approprié
3. Vérifier s'il y a une erreur de typo dans le nom

### Problème : Station dans toll_info mais pas dans les prix

**Symptôme** : La validation échoue avec des stations non utilisées.

**Solutions possibles** :
1. C'est normal si certaines pages n'ont pas encore de script de parsing
2. Vérifier si la station devrait avoir des prix associés
3. Supprimer la station de toll_info si elle n'est plus utilisée

## Scripts de Parsing Individuels

Les scripts de parsing par page se trouvent dans `page*/raw_data/parse_asf_*.py`.

**Règles importantes :**
- Utiliser la fonction `normalize_name()` pour tous les noms de stations
- Générer les 3 fichiers CSV (ou au minimum toll_info)
- Utiliser le délimiteur `;` pour tous les fichiers de sortie
- Encoder en UTF-8

## Exemple de Workflow Complet

```bash
# 1. Créer ou modifier un script de parsing
vim page_nouvelle/raw_data/parse_asf_page_nouvelle.py

# 2. Tester le script individuellement
cd page_nouvelle/raw_data
python3 parse_asf_page_nouvelle.py

# 3. Vérifier les fichiers générés
ls -l ../ASF_page_nouvelle_*.csv

# 4. Exécuter le meta-script pour tout consolider
cd ../..
python3 meta_asf.py

# 5. Vérifier les résultats
head ASF_data_price_close_2025.csv
head ASF_data_price_open_2025.csv
head ASF_toll_info.csv
```

## Auteur

Créé par OpenCode - Janvier 2026

## Licence

Fait partie du projet TollData - Données ouvertes sur les péages autoroutiers français.
