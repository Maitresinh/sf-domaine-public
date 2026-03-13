# SF Domaine Public — Pipeline éditorial

Pipeline complet pour recenser, évaluer et préparer la traduction (ou réédition de traduction existante) d'œuvres SF du domaine public sans traduction française active.

## Infrastructure

| Composant | Détail |
|-----------|--------|
| OS | Unraid 7.2 x86_64 |
| RAM | 62 Go |
| GPU | RTX 3090 (24 Go VRAM) |
| Docker | 27.5.1 / Compose v2.35.1 |
| Répertoire | `/mnt/user/sf-dp/` |

## Containers

| Container | Image | Port | Rôle |
|-----------|-------|------|------|
| `mariadb-sfdb` | mariadb:11 | 3307 | Base ISFDB complète |
| `sf-dp-tools` | sf-dp-tools:v1 | — | Container de travail Python |
| `ollama` | ollama/ollama | 11434 | gemma3:latest + qwen2.5-coder:14b |
| `sf-dp-datasette` | datasetteproject/datasette | 8001 | Exploration SQL |
| `sf-dp-streamlit` | python:3.12-slim | 8501 | GUI éditorial principal |

> **Note ops** : Python non disponible sur Unraid directement → toujours `docker exec sf-dp-tools python3`. sqlite3 CLI absent → `python3 -c "import sqlite3..."`. Patches fichiers : via `/tmp/fix.py` + `docker cp`.

## Base SQLite (`data/sf_dp.sqlite`) — 125 240 œuvres

### Colonnes principales (`works`)

| Colonne | Source | Note |
|---------|--------|------|
| `title_id` | ISFDB | PK |
| `title`, `author`, `year`, `type` | ISFDB | `type` toujours quoter — incohérence casse : minuscules EN, majuscules non-EN → fix app : `UPPER()` |
| `birth_year`, `death_year`, `birthplace` | ISFDB+Wikidata | de l'**auteur** |
| `dp_eu` | Calculé | mort avant 1956 (2026-70) |
| `dp_us`, `dp_us_reason`, `dp_us_source` | CCE | |
| `dp_fr` | Calculé | `death_year < 1948 AND dp_eu=1` |
| `has_french_vf`, `french_title` | ISFDB | |
| `lang_orig` | ISFDB | NULL = anglais (langue par défaut non renseignée) |
| `nb_langues_vf`, `langues_vf` | ISFDB | |
| `translator`, `last_vf_translator` | ISFDB | noms bruts — à enrichir (voir Traducteurs) |
| `first_vf_year`, `last_vf_year`, `last_vf_publisher`, `nb_vf_fr` | ISFDB+7_ | |
| `awards`, `award_count`, `award_score` | ISFDB | 🏆 victoire / 🏅 nomination / 📊 sondage Locus Poll |
| `synopsis` | ISFDB+Wikipedia | source dans `synopsis_source` |
| `ol_description`, `ol_subjects`, `ol_rating` | Open Library | |
| `gr_rating`, `gr_votes`, `gr_summary`, `gr_reviews_text` | Goodreads | scraping via 20_ |
| `ia_identifier`, `ia_downloads`, `ia_has_text` | Internet Archive | |
| `annualviews` | ISFDB | signal popularité |
| `isfdb_tags`, `isfdb_lists` | ISFDB | |
| `mag_title`, `mag_year` | ISFDB | short fiction magazines |

### Tables supplémentaires

- **`editorial`** : `title_id`, `status`, `priority`, `score`, `groupe`, `tags_maison`, `note`, `updated_at`
- **`noosfere_critiques`** : 8 388 entrées indexées, 709 matchées sur `works`
- **`noosfere_textes`** : textes des critiques fetchés

## Règles domaine public

- **Europe** : auteur mort avant `année_courante - 70` (avant 1956 en 2026)
- **France** : `dp_fr=1` si `death_year < 1948 AND dp_eu=1`
- **USA** : avant 1928 → DP automatique / 1928–1963 → CCE / après 1963 → protégé

## Logique traducteurs — réutilisation de traductions existantes

Une traduction française existante peut être réutilisée dans trois cas :

| Cas | Condition | Action |
|-----|-----------|--------|
| **DP traduction** | Traducteur mort depuis >70 ans | Réutilisation libre, sans négociation |
| **Droits dormants** | Traducteur mort, traduction non rééditée depuis >20 ans | Ayants droit souvent introuvables/inactifs → réutilisable en pratique ou négociation à bas coût |
| **Droits actifs** | Traducteur vivant ou traduction récemment rééditée | Hors scope — nouvelle traduction nécessaire |

**Données nécessaires par traducteur** :
- `death_year` (Wikidata + BnF `data.bnf.fr`)
- `birth_year`, nationalité
- Liste de ses traductions publiées avec dates (`last_vf_year` déjà dans `works`)
- Dernière réédition connue

**Script à créer** : `21_translators.py` — enrichissement depuis Wikidata SPARQL + BnF API, table `translators(name, birth_year, death_year, nationality, wikidata_id, bnf_id)` + lien sur `works`.

## Scripts du pipeline

| Script | Rôle | État |
|--------|------|------|
| `1_pipeline.py` | Import ISFDB→SQLite, CCE, Wikidata, awards | ✅ |
| `7_postprocess.py` | nb_editions, first_pub_year, VF françaises (filtre `author_language=FR`) | ✅ |
| `8_app.py` | GUI Streamlit — 5 pages : Catalogue, Auteurs, Prévisions DP, Sélection éditoriale, Stats | ✅ actif :8501 |
| `9_cleanup.py` | HTML entities + migrations schema | ✅ |
| `10_enrich_night.py` | Batch Wikipedia + Open Library — terminé 11/03/2026 | ✅ |
| `11_fix_awards_full.py` | Reconstruction complète texte awards | ✅ |
| `12_dp_us_check.py` | Vérification CCE | ✅ |
| `13_add_languages.py` | Ajout œuvres non-anglophones DP EU + colonne `lang_orig` | ✅ |
| `13_reviews.py` | Goodreads + Guardian | ✅ |
| `14_dp_magazines.py` | DP short fiction magazines 1928-1963, calcul `dp_fr` | ✅ |
| `15_enrich_ia.py` | Internet Archive — identifiers + downloads (874 trouvés) | ✅ |
| `16_fantlab.py` | FantLab rating/votes | ❌ abandonné (anti-scraping) |
| `17_noosfere_index.py` | Index critiques noosfere.org (8 388 entrées) | ✅ |
| `18_noosfere_critiques.py` | Fetch + extraction critiques | ✅ |
| `19_noosfere_rematch.py` | Rematch title_id manquants (709/8 388 matchés) | ✅ partiel |
| `20_gr_batch.py` | Batch nocturne Goodreads priorisé — actif depuis 13/03/2026 | ✅ en prod |
| `21_translators.py` | Enrichissement traducteurs (Wikidata + BnF) | 🔲 à créer |
| `22_synopses_wp.py` | Complétion synopses manquants via Wikipedia | 🔲 à créer |

## Lancer les scripts

```bash
# Container de travail
docker exec sf-dp-tools python3 /app/SCRIPT.py

# En arrière-plan
docker exec -d sf-dp-tools python3 /app/SCRIPT.py

# Suivre les logs
docker exec sf-dp-tools tail -f /app/data/NOM.log

# Restart GUI après modif 8_app.py
docker restart sf-dp-streamlit

# Patches fichiers (méthode fiable sur Unraid)
cat > /tmp/fix.py << 'EOF'
# script python de patch
EOF
docker cp /tmp/fix.py sf-dp-tools:/tmp/fix.py
docker exec sf-dp-tools python3 /tmp/fix.py
```

## Batch nocturne Goodreads (`20_gr_batch.py`)

- **150 livres/run**, WAIT=18s, ≈ 1h15
- Priorité 1 : DP EU ou US + sans VF + primés
- Priorité 2 : DP EU ou US + sans VF + score ≥ 10 (`annualviews/1000 + nb_langues_vf×5 + award_score`)
- Backoff exponentiel 30/60/120s sur 429, abandon si 3 blocages consécutifs
- Progression visible dans page Stats du GUI

```bash
# Cron Unraid (2h du matin)
0 2 * * * docker exec sf-dp-tools python3 /app/20_gr_batch.py
```

## Projet futur : corpus illustrations DP

**Objectif** : constituer une base d'illustrations du domaine public issues de la presse SF et fantastique, réutilisables pour des publications.

**Périmètre** :
- Pulps (Amazing Stories, Weird Tales, Astounding, etc.)
- Autres magazines SF/fantastique
- Illustrations intérieures de romans et recueils
- Couvertures

**Modèle de données envisagé** (`illustrations`) :

| Colonne | Note |
|---------|------|
| `id` | PK |
| `type` | `cover` / `interior` |
| `artist` | Nom de l'illustrateur |
| `artist_death_year` | Pour calcul DP |
| `dp_status` | DP EU / DP US / protégé |
| `publication` | Nom du magazine ou roman |
| `pub_date` | Date de publication |
| `title_id` | FK `works` — histoire illustrée (clé éditoriale) |
| `story_title` | Titre de l'histoire illustrée (texte brut) |
| `ia_identifier` | Identifiant Internet Archive |
| `thumbnail_url` | URL miniature 400px |
| `page_number` | Page dans la publication |
| `caption` | Légende originale si présente |

**Pipeline envisagé** :
1. Index Internet Archive (pulps numérisés)
2. Extraction pages via `pdf2image` / DjVu
3. Détection illustrations via YOLOv8 (déjà dans `Dockerfile.gpu`)
4. Upscaling miniatures via Real-ESRGAN
5. Matching `story_title` → `title_id` dans `works`
6. Interface dédiée dans `8_app.py` ou app séparée

**Sources Internet Archive** : collections `pulpmagazinearchive`, `amazingstories`, `weirdtales`, `astoundingsciencefiction`

## Data (non versionnée)

```
data/
├── sf_dp.sqlite          # 64 Mo — base principale
├── mysql/                # 2.8 Go — dump MariaDB ISFDB
├── cce-spreadsheets/     # 114 Mo — données CCE
├── pipeline.log
├── enrich_night.log
├── 20_gr_batch.log       # batch Goodreads nocturne
└── isfdb_schema.txt      # schéma ISFDB de référence
```
