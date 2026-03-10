
# SF Domaine Public — Pipeline éditorial

Pipeline complet pour recenser, évaluer et traduire les œuvres SF anglophones du domaine public sans traduction française.

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

```bash
# Ollama doit être connecté au network sf-dp_default
docker network connect sf-dp_default ollama
```

## Images custom

- **sf-dp-tools:v1** — python:3.12-slim + mysql-connector + sqlite-utils + pandas + requests
- **sf-dp-gpu:v1** — pytorch:2.1.0-cuda12.1 + ultralytics + pdf2image + pillow

## Base SQLite (`data/sf_dp.sqlite`) — 125 240 œuvres

### Stats clés
- Total : 125 240
- DP EU sans VF : 22 386
- DP EU+US sans VF : 18 436
- Romans sans VF : 3 158
- Avec synopsis : ~7 800 (après enrichissement)
- Avec tags : 21 743

### Colonnes principales (`works`)

| Colonne | Source | Note |
|---------|--------|------|
| `title_id` | ISFDB | PK |
| `title`, `author`, `year`, `type` | ISFDB | `type` est mot réservé SQLite → toujours quoter `"type"` |
| `birth_year`, `death_year` | ISFDB+Wikidata | |
| `dp_eu` | Calculé | mort avant 1956 |
| `dp_us`, `dp_us_reason` | CCE | |
| `has_french_vf`, `french_title` | ISFDB | |
| `awards` | title_awards FK | 🏆/🏅 avec niveaux |
| `award_count` | FK | wins+noms (niveaux 1-8) |
| `award_score` | award_titles_report | signal agrégé |
| `synopsis` | ISFDB notes FK | |
| `synopsis_source` | — | `isfdb` / `wikipedia_full` / `wikipedia_search` |
| `ol_description` | Open Library | description longue |
| `ol_subjects` | Open Library | sujets communautaires |
| `ol_rating`, `ol_votes` | Open Library | |
| `annualviews` | ISFDB | signal popularité |
| `isfdb_tags` | tag_mapping | bruit filtré |
| `isfdb_lists` | tag_mapping | listes de référence |
| `wp_searched`, `ol_searched` | — | flags enrichissement (0/1) |

### Table `editorial`

| Colonne | Note |
|---------|------|
| `title_id` | FK works |
| `status` | À évaluer / Sélectionné / En cours / Rejeté |
| `priority` | 1=⚡Urgente … 5=⬜Archive |
| `score` | /10 |
| `groupe` | groupe éditorial libre |
| `tags_maison` | tags éditoriaux libres |
| `note` | note manuelle |
| `updated_at` | timestamp |

## Schéma ISFDB — jointures awards (correct)

```sql
title_awards → awards → award_cats → award_types
  award_cats.award_cat_type_id = award_types.award_type_id
  award_level est dans la table awards (pas title_awards)
  CAST(a.award_level AS UNSIGNED) BETWEEN 1 AND 8 = victoires/nominations
  level = 1 → 🏆 victoire
  level 2-8 → 🏅 nomination/finaliste
  level 9 → éligible (exclure)
  level 10-71 → sondage Locus Poll 📊
  level 90-99 → codes spéciaux (exclure)
```

## Règles domaine public

- **Europe** : auteur mort avant `année_courante - 70` (avant 1956 en 2026)
- **France** : prorogation de guerre +8 ans pour auteurs morts avant 1948
- **USA** : avant 1928 → DP automatique / 1928–1963 → CCE / après 1963 → protégé

## Scripts du pipeline

| Script | Rôle | État |
|--------|------|------|
| `1_pipeline.py` | Import ISFDB → SQLite, fix CCE | ✅ |
| `2_fix_awards.py` | Awards (ancienne version) | remplacé par 11_ |
| `3_synopses.py` | Synopses ISFDB | ✅ |
| `4_tags.py` | Tags ISFDB | intégré dans 5_ |
| `5_enrich.py` | Enrichissement complet | ✅ |
| `6_fix_awards2.py` | Awards niveaux 1-71 | ⚠️ bug texte awards (voir 11_) |
| `7_postprocess.py` | nb_editions, first_pub_year, last_vf | ✅ |
| `8_app.py` | GUI Streamlit | ✅ actif :8501 |
| `9_cleanup.py` | HTML entities + migrations schema | ✅ |
| `10_enrich_night.py` | Batch Wikipedia + Open Library | lancer la nuit |
| `11_fix_awards_full.py` | Reconstruction complète texte awards | à lancer |

## Lancer les scripts

```bash
# Container de travail
docker exec sf-dp-tools python /app/SCRIPT.py

# En arrière-plan (nuit)
docker exec -d sf-dp-tools python /app/10_enrich_night.py

# Suivre les logs
docker exec sf-dp-tools tail -f /app/data/enrich_night.log

# Restart GUI après modif
docker restart sf-dp-streamlit
```

## MariaDB ISFDB

```bash
# Accès direct
docker exec mariadb-sfdb mariadb -uroot -pisfdb isfdb -e "VOTRE_REQUETE;"
# Credentials : user=root / password=isfdb / db=isfdb / port=3307
```

## Data (non versionnée — trop lourde)

```
data/
├── sf_dp.sqlite        # 64 Mo — base principale
├── mysql/              # 2.8 Go — dump MariaDB ISFDB
├── isfdb.sql           # 1.5 Go — dump SQL
├── cce-spreadsheets/   # 114 Mo — données CCE
├── illus_test/         # tests illustrations
├── isfdb_schema.txt    # schéma ISFDB de référence
├── pipeline.log
└── enrich_night.log
```

## TODO

- [ ] Lancer `11_fix_awards_full.py` (reconstruction awards)
- [ ] Lancer `10_enrich_night.py` (enrichissement Wikipedia + OL)
- [ ] Corriger `last_vf_year` pour filtrer éditions françaises uniquement
- [ ] Intégration Turjman : format export + POST /jobs
- [ ] Batch synopsis Ollama pour œuvres connues (nb_langues_vf >= 2)
- [ ] Tester YOLOv8 sur pages Amazing Stories
- [ ] Règle dp_fr : prorogation de guerre française (+8 ans)

## Projets futurs

- **Open Library dump** (~4 Go JSON) → Harlem Renaissance + littérature américaine
- **DNB dump** (~8 Go RDF) → littérature germanophone DP
- **works_unified.sqlite** → sources multiples (isfdb / openlibrary / dnb / bnf)
- **Illustrations** : Internet Archive pulps → YOLOv8 → thumbnails 400px → Real-ESRGAN

## Sélection éditoriale prioritaire identifiée

1. Jean Toomer — *Cane* (1923) — DP total, zéro VF FR
2. Willa Cather — *My Ántonia* (1918) — DP total
3. Nella Larsen — *Passing* (1929) — DP US probable
4. Lord Dunsany — œuvres sans VF (à requêter)
5. Arthur Machen — *The Hill of Dreams* (1907) — DP total
