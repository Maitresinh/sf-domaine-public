# SF Domaine Public — Pipeline éditorial

Pipeline complet pour recenser, évaluer et traduire les œuvres SF du domaine public sans traduction française.

## Infrastructure

| Composant | Détail |
|---|---|
| OS | Unraid 7.2 x86_64 |
| RAM | 62 Go |
| GPU | RTX 3090 (24 Go VRAM) |
| Docker | 27.5.1 / Compose v2.35.1 |
| Répertoire | `/mnt/user/sf-dp/` |

## Containers

| Container | Image | Port | Rôle |
|---|---|---|---|
| `mariadb-sfdb` | mariadb:11 | 3307 | Base ISFDB complète |
| `sf-dp-tools` | sf-dp-tools:v1 | — | Container de travail Python |
| `ollama` | ollama/ollama | 11434 | gemma3:latest + qwen2.5-coder:14b |
| `sf-dp-datasette` | datasetteproject/datasette | 8001 | Exploration SQL |
| `sf-dp-streamlit` | python:3.12-slim | 8501 | GUI éditorial principal |

> **Note** : `ps`, `pkill`, `kill` absents du container sf-dp-tools (image minimaliste).
> En cas de DB lock : `docker restart sf-dp-tools` libère tous les handles.

```bash
# Ollama connecté au network sf-dp
docker network connect sf-dp_default ollama
```

## Base SQLite (`data/sf_dp.sqlite`) — 126 679 œuvres

### Stats clés

| Périmètre | Nb |
|---|---|
| Total | 126 679 |
| DP EU anglophones sans VF FR | ~22 386 |
| DP EU non-anglophones sans VF FR | 1 439 |
| Romans (NOVEL) sans VF FR | ~3 158 |
| Avec synopsis | ~7 800 |
| Avec tags | 21 743 |
| Avec `french_title` | 10 878 (8%) |
| Avec `gr_rating` | ~1 856 |
| Avec `ia_identifier` | en cours |

### Répartition langues non-anglophones (lang_orig)

DE=530 · IT=229 · PT=122 · RU=87 · RO=79 · JA=61 · ES=54 · NL=46 · PL=40 · HU=32 · SW=18 · LA=15 · FI=15 · CZ=15 · DA=13 · YI=10 · GR=8 · BG=8...

### Table `works` — colonnes principales

| Colonne | Source | Note |
|---|---|---|
| `title_id` | ISFDB | PK |
| `title`, `author`, `year` | ISFDB | |
| `type` | ISFDB | mot réservé SQLite → toujours quoter `"type"` |
| `birth_year`, `death_year` | ISFDB | |
| `lang_orig` | 13_add_languages | langue originale (non-EN uniquement) |
| `dp_eu` | Calculé | mort avant 1956 (en 2026) |
| `dp_us`, `dp_us_reason` | CCE | |
| `dp_fr` | Calculé | prorogation guerre +8 ans |
| `dp_checked`, `dp_us_source` | 12_ | |
| `has_french_vf`, `french_title` | ISFDB | |
| `first_vf_year`, `first_vf_title` | 7_postprocess | |
| `last_vf_year`, `last_vf_title`, `last_vf_publisher` | 7_postprocess | |
| `last_vf_translator`, `nb_vf_fr` | 7_postprocess | |
| `awards`, `award_count`, `award_score` | ISFDB awards | 🏆/🏅 niveaux 1-8 |
| `synopsis`, `synopsis_source` | ISFDB notes | `isfdb` / `wikipedia_*` |
| `ol_description`, `ol_subjects` | Open Library | |
| `ol_rating`, `ol_votes`, `ol_key`, `ol_oclc` | Open Library | |
| `ol_searched` | — | flag (0/1) |
| `wikipedia_url`, `wp_searched` | Wikipedia | flag (0/1) |
| `annualviews` | ISFDB | signal popularité |
| `nb_editions`, `nb_langues_vf`, `langues_vf` | ISFDB | |
| `isfdb_tags`, `isfdb_lists` | tag_mapping | |
| `lccn` | Library of Congress | |
| `ht_rights_code`, `ht_id`, `ht_mag_code` | HathiTrust | |
| `ia_identifier`, `ia_downloads`, `ia_has_text` | Internet Archive (15_) | |
| `ia_searched` | 15_ | flag (0/1) |
| `gr_rating`, `gr_votes`, `gr_toread` | Goodreads (16_) | |
| `gr_reviews_text` | 13_reviews | JSON array extraits critiques |
| `gr_summary` | 13_reviews | synthèse Ollama 3 phrases EN |
| `gr_searched` | — | flag (0/1) |
| `guardian_url`, `guardian_title` | The Guardian (13_reviews) | |
| `guardian_date`, `guardian_snippet` | The Guardian | |
| `guardian_searched` | — | flag (0/1) |
| `goodreads_id` | 5_enrich | |
| `fantlab_rating`, `fantlab_votes` | 5_enrich | |
| `mag_title`, `mag_year`, `mag_issn` | 14_ | magazines |
| `translator`, `translator_dp` | ISFDB | |
| `first_pub_year` | 7_postprocess | |
| `isfdb_url` | — | |

### Table `editorial`

| Colonne | Note |
|---|---|
| `title_id` | FK works |
| `status` | À évaluer / Sélectionné / En cours / Rejeté |
| `priority` | 1=⚡Urgente … 5=⬜Archive |
| `score` | /10 |
| `groupe` | groupe éditorial libre |
| `tags_maison` | tags éditoriaux libres |
| `note` | note manuelle |
| `updated_at` | timestamp |

### Tables `noosfere_*`

| Table | Colonnes clés | Note |
|---|---|---|
| `noosfere_critiques` | `numlivre`, `titre_noosfere`, `auteur_noosfere`, `lettre`, `title_id`, `nb_critiques`, `critique_fetched` | 8 388 entrées, index A-Z |
| `noosfere_textes` | `id`, `numlivre`, `chroniqueur`, `texte`, `is_serie` | 1 ligne par critique |

## Schéma ISFDB — jointures awards

```sql
title_awards → awards → award_cats → award_types
  award_cats.award_cat_type_id = award_types.award_type_id
  award_level est dans la table awards (pas title_awards)
  CAST(a.award_level AS UNSIGNED) BETWEEN 1 AND 8 = victoires/nominations
  level = 1    → 🏆 victoire
  level 2-8   → 🏅 nomination/finaliste
  level 9     → éligible (exclure)
  level 10-71 → sondage Locus Poll 📊
  level 90-99 → codes spéciaux (exclure)
```

## Règles domaine public

| Zone | Règle |
|---|---|
| **Europe** | auteur mort avant `année_courante - 70` (avant 1956 en 2026) |
| **France** | prorogation de guerre +8 ans pour auteurs morts avant 1948 |
| **USA avant 1928** | DP automatique |
| **USA 1928–1963** | vérification CCE (12_dp_us_check.py) |
| **USA après 1963** | protégé |
| **Non-anglophones** | dp_eu calculé, dp_us=0 par défaut (CCE non applicable) |

## Scripts du pipeline

| Script | Rôle | État |
|---|---|---|
| `1_pipeline.py` | Import ISFDB → SQLite (EN uniquement), calcul DP EU/US/CCE | ✅ |
| `2_fix_awards.py` | Awards ancienne version | ⚠️ remplacé par 11_ |
| `3_synopses.py` | Synopses ISFDB notes | ✅ |
| `4_tags.py` | Tags ISFDB | ✅ intégré dans 5_ |
| `5_enrich.py` | Enrichissement Wikipedia + Open Library + Fantlab | ✅ |
| `6_fix_awards2.py` | Awards niveaux 1-71 | ⚠️ remplacé par 11_ |
| `7_postprocess.py` | nb_editions, first_pub_year, VF FR (filtré title_language=22) | ✅ |
| `8_app.py` | GUI Streamlit éditorial | ✅ actif :8501 |
| `9_cleanup.py` | HTML entities + migrations schéma | ✅ |
| `10_enrich_night.py` | Batch Wikipedia + Open Library (nuit) | ✅ |
| `11_fix_awards_full.py` | Reconstruction complète texte awards | ✅ |
| `12_dp_us_check.py` | Vérification DP US via CCE + HathiTrust | ✅ |
| `13_add_languages.py` | Ajout œuvres non-anglophones DP EU sans VF FR (+1 439) | ✅ |
| `13_reviews.py` | Goodreads + Guardian API + synthèse Ollama | ⚠️ legacy |
| `14_dp_magazines.py` | Magazines DP (ISFDB pulps) | ✅ |
| `15_enrich_ia.py` | Internet Archive : ia_identifier, ia_downloads, ia_has_text | ✅ |
| `16_enrich_goodreads.py` | Goodreads ratings : gr_rating, gr_votes, gr_toread | ✅ |
| `16_fantlab.py` | Fantlab ratings (RU) | ✅ |
| `17_noosfere_index.py` | Index critiques noosfere.org A-Z → 8 388 entrées | ✅ |
| `18_noosfere_critiques.py` | Fetch textes critiques → noosfere_textes | 🔄 en cours |
| `19_noosfere_rematch.py` | Rematch title_id via "Titre original" dans fiche noosfere | 📋 TODO |

## Lancer les scripts

```bash
# Container de travail (volume monté — pas de docker cp nécessaire)
# Écrire dans /mnt/user/sf-dp/ = disponible dans /app/ du container

docker exec sf-dp-tools python3 /app/SCRIPT.py

# En arrière-plan (nuit)
docker exec -d sf-dp-tools python3 /app/SCRIPT.py

# Suivre progression
docker exec sf-dp-tools python3 -c "
import sqlite3
conn = sqlite3.connect('/app/data/sf_dp.sqlite')
done = conn.execute('SELECT COUNT(*) FROM noosfere_critiques WHERE critique_fetched=1').fetchone()[0]
print(f'noosfere: {done}/8388')
"

# En cas de DB lock : redémarrer le container
docker restart sf-dp-tools
```

## MariaDB ISFDB

```bash
docker exec mariadb-sfdb mariadb -uroot -pisfdb isfdb -e "VOTRE_REQUETE;"
# Credentials : user=root / password=isfdb / db=isfdb / port=3307
# Colonne année : title_copyright (DATE) → YEAR(title_copyright)
# Langue : title_language (FK languages.lang_id) — EN=17, FR=22
```

## Data (non versionnée — trop lourde)

```
data/
├── sf_dp.sqlite        # ~100 Mo — base principale
├── mysql/              # 2.8 Go — dump MariaDB ISFDB
├── isfdb.sql           # 1.5 Go — dump SQL
├── cce-spreadsheets/   # 114 Mo — données CCE
├── isfdb_schema.md     # schéma ISFDB de référence
├── pipeline.log
├── reviews.log
└── enrich_night.log
```

## TODO

- `19_noosfere_rematch.py` : rematch `title_id IS NULL` via regex `Titre original : X, année`
- Afficher critiques noosfere dans `8_app.py` (onglet dédié)
- Corriger `last_vf_year` pour filtrer éditions françaises uniquement (filtre `title_language=22`)
- Lancer Guardian sur nouvelles œuvres non-anglophones (13_reviews.py étape 2)
- Batch synopsis Ollama pour œuvres connues (`nb_langues_vf >= 2`)

## Projets futurs

- **Open Library dump** (~4 Go JSON) → Harlem Renaissance + littérature américaine
- **DNB dump** (~8 Go RDF) → littérature germanophone DP
- **works_unified.sqlite** → sources multiples (isfdb / openlibrary / dnb / bnf)
- **Illustrations** : Internet Archive pulps → YOLOv8 → thumbnails → Real-ESRGAN
- **Intégration Turjman** : format export + POST /jobs

## Sélection éditoriale prioritaire identifiée

1. Jean Toomer — *Cane* (1923) — DP total, zéro VF FR
2. Willa Cather — *My Ántonia* (1918) — DP total
3. Nella Larsen — *Passing* (1929) — DP US probable
4. Lord Dunsany — œuvres sans VF (à requêter)
5. Arthur Machen — *The Hill of Dreams* (1907) — DP total
6. Karel Čapek — *War with the Newts* (1936) — DP EU, VF FR ancienne
