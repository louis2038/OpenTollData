# Documentation du Schéma JSON pour les Réseaux de Péage

## Vue d'ensemble

Ce document décrit le schéma JSON (`toll_network_schema.json`) utilisé pour valider les données de réseau de péage générées par `make_toll_json.py`.

## Structure du JSON

### Champs principaux

| Champ | Type | Requis | Description |
|-------|------|--------|-------------|
| `date` | string | ✅ | Date au format DD/MM/YYYY |
| `version` | string | ✅ | Version du format de données |
| `name` | string | ✅ | Nom du format de tarification |
| `list_of_operator` | array | ✅ | Liste des opérateurs de péage |
| `list_of_toll` | array | ✅ | Liste de tous les noms de péages |
| `currency` | string | ✅ | Code devise ISO 4217 (ex: EUR, USD) |
| `networks` | array | ✅ | Composantes connexes des réseaux fermés |
| `toll_description` | object | ✅ | Informations détaillées sur chaque péage |
| `open_toll_price` | object | ✅ | Tarification des péages ouverts (tarif forfaitaire) |

### Structure détaillée

#### 1. Networks (Réseaux)

Chaque réseau représente une composante connexe de péages fermés :

```json
{
  "network_name": "component_1",
  "tolls": ["TOLL_A", "TOLL_B", "TOLL_C"],
  "connection": {
    "TOLL_A": {
      "TOLL_B": {
        "distance": "150.5",
        "price": {
          "class_1": "12.50",
          "class_2": "18.75",
          "class_3": "25.00",
          "class_4": "31.25",
          "class_5": "37.50"
        }
      }
    }
  }
}
```

#### 2. Toll Description (Description des péages)

Informations géographiques et opérationnelles pour chaque péage :

```json
{
  "TOLL_NAME": {
    "operator_ref": "A1",
    "lat": "48.8566",
    "lon": "2.3522",
    "operator": "Autoroutes Paris-Rhin-Rhône",
    "type": "close",
    "node_id": ["123456", "789012"],
    "ways_id": ["345678"]
  }
}
```

**Types de péage :**
- `"close"` : Péage fermé (tarification basée sur la distance)
- `"open"` : Péage ouvert (tarif forfaitaire)

#### 3. Open Toll Price (Prix des péages ouverts)

Tarification forfaitaire pour les péages ouverts :

```json
{
  "OPEN_TOLL": {
    "distance": "10.0",
    "price": {
      "class_1": "2.50",
      "class_2": "3.75",
      "class_3": "5.00",
      "class_4": "6.25",
      "class_5": "7.50"
    }
  }
}
```

#### 4. Classes de véhicules

Les prix sont définis pour 5 classes de véhicules :

| Classe | Description typique |
|--------|---------------------|
| class_1 | Véhicules légers (voitures) |
| class_2 | Véhicules avec remorque ou camping-cars |
| class_3 | Autocars et bus |
| class_4 | Poids lourds 2 essieux |
| class_5 | Poids lourds 3+ essieux |

## Utilisation

### 1. Génération avec validation automatique

Pour générer un JSON et le valider automatiquement :

```bash
python make_toll_json.py \
    --close data/AREA_data_price_close.csv \
    --open data/AREA_data_price_open.csv \
    --info data/AREA_toll_info.csv \
    --out output/toll_network.json \
    --version 1.0 \
    --name price_format \
    --currency EUR \
    --validate
```

### 2. Validation d'un fichier existant

Pour valider un fichier JSON existant :

```bash
python validate_toll_json.py toll_network.json
```

Avec résumé des données :

```bash
python validate_toll_json.py --summary toll_network.json
```

Avec un schéma personnalisé :

```bash
python validate_toll_json.py --schema custom_schema.json toll_network.json
```

### 3. Installation des dépendances

Pour utiliser la validation, installez le module `jsonschema` :

```bash
pip install jsonschema
```

## Règles de validation

### 1. Format des dates
- Pattern : `DD/MM/YYYY`
- Exemple : `"25/12/2024"`

### 2. Code devise
- Pattern : 3 lettres majuscules (ISO 4217)
- Exemples : `"EUR"`, `"USD"`, `"GBP"`

### 3. Distances et prix
- Format : Nombres décimaux sous forme de chaîne
- Pattern : `^\d+(\.\d+)?$`
- Exemples : `"150.5"`, `"12.50"`, `"100"`

### 4. Noms de réseau
- Pattern : `component_N` où N est un nombre
- Exemples : `"component_1"`, `"component_2"`

### 5. Cohérence des données

Le script `make_toll_json.py` vérifie automatiquement :

- ✅ Tous les noms dans `price_close` existent dans `toll_info`
- ✅ Tous les noms dans `price_open` existent dans `toll_info`
- ✅ Les péages dans `price_close` ont `type == "close"`
- ✅ Les péages dans `price_open` ont `type == "open"`
- ✅ Les valeurs numériques sont valides (distances, prix)

## Exemples d'erreurs courantes

### Erreur 1 : Format de date invalide

```json
{
  "date": "2024-12-25"  // ❌ Format incorrect
}
```

**Correction :**
```json
{
  "date": "25/12/2024"  // ✅ Format correct
}
```

### Erreur 2 : Code devise invalide

```json
{
  "currency": "Euro"  // ❌ Pas au format ISO 4217
}
```

**Correction :**
```json
{
  "currency": "EUR"  // ✅ Code ISO correct
}
```

### Erreur 3 : Type de péage incorrect

```json
{
  "type": "opened"  // ❌ Valeur non autorisée
}
```

**Correction :**
```json
{
  "type": "open"  // ✅ Valeur valide (open ou close)
}
```

### Erreur 4 : Prix manquant

```json
{
  "price": {
    "class_1": "10.50",
    "class_2": "15.75"
    // ❌ class_3, class_4, class_5 manquants
  }
}
```

**Correction :**
```json
{
  "price": {
    "class_1": "10.50",
    "class_2": "15.75",
    "class_3": "20.00",
    "class_4": "25.00",
    "class_5": "30.00"
  }
}
```

## Intégration dans un pipeline

### Pipeline de validation complet

```bash
#!/bin/bash

# 1. Générer le JSON avec validation
python make_toll_json.py \
    --close data/FR_data_price_close.csv \
    --open data/FR_data_price_open.csv \
    --info data/FR_toll_info.csv \
    --out output/france_tolls.json \
    --version 2.0 \
    --name france_highways \
    --currency EUR \
    --validate

# 2. Si la génération réussit, faire une validation détaillée
if [ $? -eq 0 ]; then
    python validate_toll_json.py --summary output/france_tolls.json
else
    echo "Erreur lors de la génération du JSON"
    exit 1
fi
```

### Validation en Python

```python
import json
import jsonschema
from jsonschema import validate

# Charger le schéma
with open("toll_network_schema.json") as f:
    schema = json.load(f)

# Charger les données
with open("toll_network.json") as f:
    data = json.load(f)

# Valider
try:
    validate(instance=data, schema=schema)
    print("✅ Validation réussie!")
except jsonschema.ValidationError as e:
    print(f"❌ Erreur: {e.message}")
    print(f"Chemin: {' -> '.join(str(p) for p in e.path)}")
```

## Personnalisation du schéma

Pour adapter le schéma à vos besoins :

1. **Modifier le nombre de classes de véhicules** :
   Éditez la définition `priceClasses` dans le schéma

2. **Ajouter des champs personnalisés** :
   Ajoutez de nouvelles propriétés dans les sections appropriées

3. **Changer les contraintes de validation** :
   Modifiez les patterns regex ou ajoutez des contraintes `minimum`/`maximum`

4. **Utiliser un schéma personnalisé** :
   ```bash
   python make_toll_json.py ... --validate --schema custom_schema.json
   ```

## Support et contribution

Pour signaler des problèmes ou suggérer des améliorations :

1. Vérifiez que vos fichiers CSV respectent le format attendu
2. Consultez les messages d'erreur détaillés
3. Utilisez l'option `--summary` pour obtenir des statistiques
4. Documentez les cas d'usage spécifiques à votre région

## Licence

Ce schéma et les outils de validation associés sont fournis tels quels pour faciliter l'échange de données sur les réseaux de péage.