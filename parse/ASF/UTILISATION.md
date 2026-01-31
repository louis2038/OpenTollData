# Guide d'Utilisation Rapide - Meta-Scripts ASF

## 🚀 Utilisation Simple

### Option 1 : Tout exécuter en une seule commande

```bash
cd /home/louis/Documents/programation/Projet_routing/Git_TollData/parse/ASF
python3 meta_asf.py
```

**Cela va :**
1. Exécuter tous les scripts de parsing (22 scripts)
2. Fusionner tous les CSV
3. Valider la cohérence
4. Générer les 3 fichiers consolidés

### Option 2 : Exécution étape par étape

#### Étape 1 : Exécuter uniquement les scripts de parsing

```bash
python3 run_all_page_scripts.py
```

#### Étape 2 : Fusionner manuellement les fichiers

```bash
# Close prices
python3 merge_csv_files.py close ASF_data_price_close_2025.csv \
    page1/ASF_page1_data_price_close_2025.csv \
    page2/ASF_page2_data_price_close_2025.csv \
    page3/ASF_page3_data_price_close_2025.csv \
    page4/ASF_page4_data_price_close_2025.csv \
    page5/ASF_page5_data_price_close_2025.csv

# Open prices
python3 merge_csv_files.py open ASF_data_price_open_2025.csv \
    page1/ASF_page1_data_price_open_2025.csv \
    page3/ASF_page3_data_price_open_2025.csv \
    page4/ASF_page4_data_price_open_2025.csv \
    page5/ASF_page5_data_price_open_2025.csv

# Toll info
python3 merge_csv_files.py toll_info ASF_toll_info.csv \
    page1/ASF_page1_toll_info.csv \
    page2/ASF_page2_toll_info.csv \
    page3/ASF_page3_toll_info.csv \
    page4/ASF_page4_toll_info.csv \
    page5/ASF_page5_toll_info.csv \
    page6/ASF_page6_toll_info.csv \
    page7/ASF_page7_toll_info.csv \
    page8_9/ASF_page8_9_toll_info.csv \
    page8_9/ASF_page8_part1_toll_info.csv
```

#### Étape 3 : Valider la cohérence

```bash
python3 validate_triplet.py \
    ASF_data_price_close_2025.csv \
    ASF_data_price_open_2025.csv \
    ASF_toll_info.csv
```

## 📊 Vérifier les Résultats

```bash
# Compter les lignes
wc -l ASF_*.csv

# Voir les premières lignes
head -20 ASF_data_price_close_2025.csv
head -20 ASF_data_price_open_2025.csv
head -20 ASF_toll_info.csv

# Vérifier l'encodage et le délimiteur
file ASF_*.csv
head -1 ASF_*.csv
```

## 🔍 Déboguer les Erreurs

### Si la validation échoue

Le script affichera exactement quelles stations sont problématiques :

```
❌ 12 station(s) présente(s) dans les fichiers de prix mais ABSENTE(S) de toll_info:
  - BAYONNE SUD,,0.8,1.3,1.6,2.1,0.4 [open]
  - BIARRITZ,,1.2,2.0,2.9,3.8,0.7 [open]
  ...
```

**Solutions :**
1. Vérifier le fichier source avec `grep`
2. Corriger le script de parsing correspondant
3. Ré-exécuter le script de parsing
4. Relancer la fusion et validation

### Trouver quel script génère une station

```bash
# Chercher dans tous les fichiers CSV
grep -r "BAYONNE SUD" page*/ASF_*.csv

# Résultat : page5/ASF_page5_data_price_open_2025.csv
# Donc le script problématique est : page5/raw_data/parse_asf_open_page5_*.py
```

## 🎯 Cas d'Usage Courants

### Ajouter une nouvelle page

1. Créer `pageX/raw_data/parse_asf_pageX.py`
2. Exécuter le script individuellement pour tester
3. Relancer `python3 meta_asf.py` pour tout regénérer

### Corriger des données d'une page

1. Modifier le script `pageX/raw_data/parse_asf_*.py`
2. Relancer `python3 meta_asf.py`

### Vérifier seulement la cohérence (sans ré-exécuter le parsing)

```bash
# Commenter l'étape 1 dans meta_asf.py ou utiliser validate_triplet.py directement
python3 validate_triplet.py \
    ASF_data_price_close_2025.csv \
    ASF_data_price_open_2025.csv \
    ASF_toll_info.csv
```

## 📝 Notes Importantes

1. **Le script s'arrête immédiatement en cas d'erreur** - C'est voulu pour éviter de générer des données incohérentes
2. **Les noms sont la clé primaire** - Assurez-vous qu'ils sont normalisés de façon cohérente
3. **Les fichiers sont en UTF-8 avec délimiteur `;`** - Tous les fichiers de sortie suivent ce format
4. **Les doublons sont automatiquement supprimés** - Pas besoin de s'en préoccuper

## 🆘 Aide

Voir le fichier `README_META_SCRIPTS.md` pour la documentation complète.

