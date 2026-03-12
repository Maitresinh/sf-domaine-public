# Journal de sessions
# Journal de sessions

## Session 2 — 10 mars 2026

### Bugs corrigés dans 8_app.py
- `KeyError: 'type'` page Prévisions DP → aliasé `"type" AS work_type` partout
- `NameError: title_q` fiche détail → variables définies en tête d'expander
- `TypeError: '>' not supported` awards → `int()` cast sur `award_count`/`award_score`

### Améliorations GUI (8_app.py → v3)
- Tags : multiselect avec compteurs, mode ET/OU, exclusion
- Awards : filtre par niveau (🏆/🏅/📊) + filtre par prix (Hugo, Nebula…)
- Séries : recherche textuelle avec session_state
- Sélection éditoriale refonte complète : score /10, priorité, groupes, tags maison, suppression avec confirmation, export CSV par groupe
- Fiche DP : bloc documenté avec source et liens de vérification par cas
- Filtre "DP US probable (non trouvé CCE)" ajouté

### Nettoyage données (9_cleanup.py)
- 141 auteurs + 77 titres + 55 synopsis : HTML entities nettoyés (`&#268;` → `Č` etc.)
- Colonne `synopsis_source` ajoutée (`isfdb` / `wikipedia_full` / `wikipedia_search`)
- 371 synopsis enrichis depuis Wikipedia (API MediaWiki, intro complète)
- Fix User-Agent Wikipedia (sans lui : 500 erreurs)

### Fix awards (11_fix_awards_full.py)
- Diagnostic : 2019 œuvres avec `award_count > 0` mais `awards` vide
- Cause : `6_fix_awards2.py` incluait les niveaux 9 (éligibles) dans le comptage
- Fix : niveaux 9 remis à `award_count=0`, texte reconstruit depuis MariaDB
- Schéma correct confirmé : `award_level` est dans table `awards` (pas `title_awards`)
  `CAST(a.award_level AS UNSIGNED) BETWEEN 1 AND 8` = victoires/nominations
- Résultat : 3271 œuvres avec texte awards cohérent, 0 incohérence

### Découverte majeure : bug DP US
- 34 483 œuvres 1928-1963 avec `dp_us=NULL` ("non trouvé CCE")
- Cause : Stanford CCE couvre Class A (livres) uniquement — correct pour nouvelles
- **Pour les romans** : "non trouvé CCE" = non renouvelé = DP US légalement solide
- Fix dans 12_dp_us_check.py : 3591 romans → `dp_us=1`
- Sources exclues : Internet Archive (trop d'erreurs, lawsuit perdu 2024)

### Script enrichissement nuit (10_enrich_night.py)
- Étape 1 : Wikipedia URL connue → synopsis intro complète (MediaWiki API)
- Étape 2 : Wikipedia search pour œuvres sans URL
- Étape 3 : Open Library → description longue + sujets + note
- Colonnes ajoutées : `ol_description`, `ol_subjects`, `ol_rating`, `ol_votes`
- Flags reprise : `wp_searched`, `ol_searched` (évite retraitement)
- En cours ce soir (~10 000 ops, ~3h total)

### Script vérification DP (12_dp_us_check.py)
- Étape 1 : Romans non trouvés CCE → `dp_us=1` (règle légale directe)
- Étape 2 : NYPL CCE extended (GitHub) — toutes classes, détecte protégés
- Étape 3 : Open Library → OCLC → HathiTrust rightsCode (bibliothécaires)
- Étape 4 : Marquage restants "à vérifier manuellement"
- Colonnes ajoutées : `dp_us_source`, `ht_rights_code`, `ht_id`, `ol_oclc`, `lccn`, `dp_checked`
- À lancer après fin de 10_enrich_night.py

### GitHub
- Repo privé créé : github.com/Maitresinh/sf-domaine-public
- Premier push propre : 30 KiB (data lourde exclue)
- Credentials MariaDB : user=root / password=**isfdb** / db=isfdb / port=3307

### Nouvelles colonnes ajoutées à `works`
| Colonne | Type | Source |
|---------|------|--------|
| `synopsis_source` | TEXT | `isfdb`/`wikipedia_full`/`wikipedia_search` |
| `ol_description` | TEXT | Open Library description longue |
| `ol_subjects` | TEXT | Open Library sujets (20 max) |
| `ol_rating` | REAL | Open Library note |
| `ol_votes` | INTEGER | Open Library votes |
| `ol_key` | TEXT | Clé Open Library `/works/OLXXXXW` |
| `wp_searched` | INTEGER | Flag 0/1 Wikipedia déjà tenté |
| `ol_searched` | INTEGER | Flag 0/1 OL déjà tenté |
| `dp_us_source` | TEXT | Source confirmation DP US |
| `ht_rights_code` | TEXT | Code brut HathiTrust |
| `ht_id` | TEXT | HathiTrust item ID |
| `ol_oclc` | TEXT | OCLC number |
| `lccn` | TEXT | Library of Congress Control Number |
| `dp_checked` | INTEGER | Flag traitement 12_dp_us_check.py |

### Nouvelles colonnes ajoutées à `editorial`
| Colonne | Type | Note |
|---------|------|------|
| `priority` | INTEGER | 1=⚡Urgente … 5=⬜Archive |
| `score` | INTEGER | /10 |
| `groupe` | TEXT | groupe éditorial libre |
| `tags_maison` | TEXT | tags éditoriaux libres |
## Session 3 — 10 mars 2026 (soir)

### Confirmation fin de 10_enrich_night.py
- Terminé à 20:26:54 après ~8400 ops
- Synopsis total : 9663 (vs 7438 avant)
  - isfdb : inchangé
  - wikipedia_full : 582
  - wikipedia_search : 1797
- OL description : 186 / OL sujets : 576 / OL rating : 137
- Flags wp_searched / ol_searched correctement posés (reprise possible)

### Problèmes rencontrés sur 12_dp_us_check.py
- `sqlite3` absent du container sf-dp-tools → utiliser `python3 -c "import sqlite3..."` à la place
- `pkill`, `ps`, `kill` absents du container (image python:3.12-slim ultra-minimale)
- Multiples instances lancées par erreur → `database is locked` (OperationalError ligne 50)
- Fix : `docker restart sf-dp-tools` + `flock /app/data/12.lock` pour éviter les doublons
- Logs du projet dans `/app/data/*.log` (pas `/app/logs/`)

### État DB après étape 1 du script 12
| Métrique | Avant | Après étape 1 |
|---|---|---|
| dp_us_confirme | 24 079 | 27 670 (+3 591) |
| dp_us_protege | 66 678 | 66 678 |
| a_verifier (1928-1963, NULL) | 34 483 | 30 892 |
| via_cce | — | 3 591 |
| via_hathitrust | 0 | 0 (étape 3 en cours) |

### Repo GitHub
- Passé en public : https://github.com/Maitresinh/sf-domaine-public

### Rappels techniques
- Toujours utiliser `flock /app/data/NOM.lock` pour les scripts longs en `-d`
- Vérifier qu'aucune instance ne tourne avant de relancer (pas de ps/kill → restart)
- Logs dans `/app/data/` (volume monté), pas `/app/logs/`
- sqlite3 CLI absent → python3 pour toutes les requêtes DB
## Session 3 — 10 mars 2026 (soir)

### Confirmation fin de 10_enrich_night.py
- Terminé à 20:26:54 après ~8400 ops
- Synopsis total : 9663 (vs 7438 avant)
  - wikipedia_full : 582 / wikipedia_search : 1797
- OL description : 186 / OL sujets : 576 / OL rating : 137

### Problèmes rencontrés sur 12_dp_us_check.py
- sqlite3, pkill, ps, kill absents du container (python:3.12-slim minimal)
- Multiples instances → database is locked
- Fix : docker restart + flock /app/data/12.lock
- Logs dans /app/data/*.log (pas /app/logs/)

### État DB après étape 1 du 12
- dp_us_confirme : 24 079 → 27 670 (+3 591 romans non trouvés CCE)
- a_verifier : 34 483 → 30 892
- Étape 3 (OL → OCLC → HathiTrust) en cours

### Repo GitHub passé public

### Schéma MariaDB ISFDB — corrections importantes
Découvertes lors du check awards 1928-1963 :

| Ce qu'on pensait | Réalité |
|---|---|
| `title_year` | N'existe pas → `YEAR(title_copyright)` |
| `title_author` | N'existe pas dans `titles` → join `canonical_author` |
| `award_level` type INT | C'est `mediumtext` → toujours `CAST(award_level AS UNSIGNED)` |
| `title_ttype` valeurs | Enum uppercase : `NOVEL`, `SHORTFICTION`, `SS` n'existe pas |

Types valides title_ttype : NOVEL, SHORTFICTION, NOVELETTE absent (→ SHORTFICTION),
COLLECTION, ANTHOLOGY, CHAPBOOK, SERIAL, OMNIBUS, COVERART, INTERIORART...

award_year est de type DATE (pas INT) → `YEAR(a.award_year)` si besoin.

### Analyse awards 1928-1963 — pépites identifiées
Requête MariaDB corrigée (YEAR(title_copyright), CAST award_level) révèle
des Hugo winners absents du catalogue SQLite car dp_us=NULL (script 12 en cours) :

- Way Station — Clifford Simak (1963) 🏆 Hugo
- The Man in the High Castle — Philip K. Dick (1962) 🏆 Hugo
- The Long Afternoon of Earth — Brian Aldiss (1962) 🏆 Hugo
- A Wrinkle in Time — Madeleine L'Engle (1962) 🏆 Newbery
- Stranger in a Strange Land — Heinlein (1961) 🏆 Hugo + Prometheus
- Starship Troopers — Heinlein (1959) 🏆 Hugo
- A Canticle for Leibowitz — Walter M. Miller Jr. (1959) 🏆 Hugo
- A Case of Conscience — James Blish (1958) 🏆 Hugo
- A Clockwork Orange — Anthony Burgess (1962) 🏆 Prometheus

Ces œuvres ont dp_eu=0 (auteurs morts après 1955) mais seront dp_us=1
après fin du script 12 (non renouvelé CCE = DP US légal).
→ Seront visibles dans le catalogue GUI après fin du 12.

### Chiffres synopsis DP sans VF (état après 10_enrich_night)
- DP sans VF total     : 29 769
- Avec synopsis        : 3 651 (12%)
- Sans synopsis        : 26 118
  dont wp_searched=1   : 1 269 (Wikipedia tenté, rien trouvé)
  dont jamais cherché  : 24 849 → priorité batch suivant

### Chantiers identifiés après check awards/synopsis (session 3 suite)

#### MariaDB — schéma corrigé
- `title_year` n'existe pas → `YEAR(title_copyright)`
- `award_level` est mediumtext → toujours `CAST(award_level AS UNSIGNED)`
- Les critiques ISFDB sont dans `titles` type REVIEW + `title_relationships.review_id`
  mais sans texte exploitable (juste métadonnées de publication)

#### Script 13_reviews.py — conçu, à lancer après fin du 12
- Étape 1 : Goodreads scraping (1817 œuvres avec goodreads_id)
  → gr_rating, gr_votes, gr_toread, gr_reviews_text (JSON, 5 extraits max)
- Étape 2 : The Guardian API (clé : 8146d1a6-eaaa-4feb-88de-d31af3ae6b6f)
  → guardian_url, guardian_title, guardian_date, guardian_snippet
  → ciblé : primés + annualviews>500 + nb_langues_vf>=3 (3000 max)
- Étape 3 : Ollama gemma3 synthèse critiques GR (si ≥2 reviews scraped)
  → gr_summary — compression textes réels, pas génération

#### Nouvelles colonnes works prévues par 13_reviews.py
gr_rating, gr_votes, gr_toread, gr_reviews_text, gr_summary,
gr_searched, guardian_url, guardian_title, guardian_date,
guardian_snippet, guardian_searched

### Résultats finaux script 12_dp_us_check.py
Terminé à 23:37 — deux instances (idempotent, résultat correct)

| Métrique | Avant | Après |
|---|---|---|
| dp_us=1 total | 24 079 | 27 686 |
| source cce_stanford_novel | 0 | 3 591 |
| source hathitrust | 0 | 87 |
| dp_us=NULL 1928-1963 | 34 483 | 30 805 |
| dp_checked=1 | 0 | 37 106 |
| DP sans VF romans | ~3 158 | 6 486 |
| DP sans VF primés | 39 | 40 |

Notes :
- Romans sans VF doublés grâce à règle CCE Class A (étape 1)
- 30 805 NULL restants = short fiction/novelettes, non couverts (normal)
- Hugo winners 1928-1963 maintenant dans catalogue mais la plupart ont une VF
- HathiTrust : 87 confirmations via OCLC (faible — beaucoup sans OCLC dans OL)

### Prochaine étape : 13_reviews.py
Lancer après vérification GUI : Goodreads + Guardian + synthèse Ollama

### Croisement SQLite ↔ magazines MariaDB (test_mag2.py)
- 35 991 short fiction magazines 1928-1963 dans MariaDB
- 12 982 short fiction total dans notre SQLite
- Overlap (dans SQLite ET dans un magazine) : 242
- Cibles dp_us=NULL dans l'overlap : 215 → pipeline HathiTrust magazines
- 12 740 short fiction SQLite sans pub_content magazine
  → publiés en recueil/anthologie, pas en magazine → règle différente

### Conclusion stratégie 14_dp_magazines.py
Volume réel traitable : 215 œuvres (pas 2 595)
Approche : pour chaque title_id overlap, retrouver le magazine + numéro
→ interroger HathiTrust par titre magazine + année → rightsCode
→ si pd : dp_us=1 sur toutes les nouvelles du numéro dans notre SQLite

## Session 4 — 11 mars 2026 (après-midi)

### Script 13_reviews.py — TERMINÉ (07:27)
| Métrique | Résultat |
|---|---|
| GR rating récupéré | 1816/1817 |
| GR reviews texte | 1717 |
| GR summary Ollama | 426 (synthèse critiques GR réelles, PAS de synopsis générés) |
| Guardian articles | 352 |
| Note moyenne DP/sVF | 3.49 |

⚠️ Ollama dans 13_reviews.py = synthèse de critiques Goodreads scraped uniquement.
   Colonne gr_summary ≠ synopsis. Les synopsis viennent exclusivement de ISFDB + Wikipedia.

### Script 14_dp_magazines.py — EN COURS / À REVOIR
- Fichier créé et lancé
- Bugs corrigés : LEFT JOIN magazine (colonne inexistante), requête bulk vs boucle 29k, base_mag()
- Problème fondamental identifié : HathiTrust ic ≠ "protégé" — juste "on ne sait pas"
- Approche à revoir complètement avant relance

### Révision stratégie DP magazines — PRIORITÉ SESSION 5
Deux niveaux de copyright distincts :
  1. Magazine (compilation) — Class B — renouvelé par l'éditeur
  2. Nouvelles individuelles — Class A — renouvelées par l'auteur séparément

Sources à interroger (jamais fait) :
  - UPenn firstperiod.html → liste réelle des périodiques ayant renouvelé
  - UPenn decisions.html → règles légales exactes pour sériaux
  - Stanford CCE Class B (périodiques) séparé de Class A

Fait en session 4 : curl firstperiod.html + decisions.html → résultats à analyser

Taux de non-renouvellement historique pulps : ~85% (Hirtle, Landes)
→ La majorité des pulps SF n'ont PAS renouvelé → nouvelles = DP US probable

### Nouvelles colonnes ajoutées par 13_reviews.py
gr_rating, gr_votes, gr_toread, gr_reviews_text, gr_summary, gr_searched,
guardian_url, guardian_title, guardian_date, guardian_snippet, guardian_searched

### Nouvelles colonnes ajoutées par 14_dp_magazines.py
mag_title, mag_year, mag_issn, ht_mag_code

### TODO session 5
1. Analyser résultats UPenn firstperiod.html + decisions.html
2. Réécrire 14_dp_magazines.py avec vraies sources CCE Class B
3. Intégrer GR/Guardian dans 8_app.py (fiche détail)
4. Mettre à jour README (stats obsolètes)

### Mécanique juridique copyright magazines — clarification session 4

Loi applicable : Copyright Act 1909 (œuvres 1928-1963)
Durée : 28 ans + renouvellement 28 ans. Sans renouvellement → DP à 28 ans.

Deux copyrights INDÉPENDANTS :
  - Magazine (compilation) : Class B, renouvelé par l'éditeur
  - Nouvelle individuelle : Class A, renouvelée par l'auteur séparément

Règle clé : le renouvellement du magazine NE PROTÈGE PAS les nouvelles individuelles.
Seul le CCE Class A de l'auteur compte pour chaque nouvelle.

Cas pratique Amazing Stories 1935 :
  - Compilation : pas renouvelée avant mai 1954 → numéro 1935 = DP compilation
  - Nouvelle de Asimov dedans : si Asimov a renouvelé en ~1963 → protégée
  - Nouvelle de auteur obscur : si non renouvelée en ~1963 → DP

Données UPenn acquises :
  - Amazing Stories : compilation DP avant mai 1954, ~257 contributions renouvelées
  - Planet Stories : compilation 100% DP (jamais renouvelée), ~66 contributions renouvelées
  - Famous Fantastic Mysteries : compilation DP avant jan. 1940, ~1 contribution renouvelée
  - Weird Tales : compilation DP avant fév. 1931
  - Astounding : compilation DP avant oct. 1933

### 14_dp_magazines.py v2 — stratégie révisée
Même logique que script 12 étape 1 (romans CCE Class A),
étendue à la short fiction :
  - Non trouvé CCE Class A → dp_us=1
  - Bonus : croiser avec liste contributions renouvelées UPenn par magazine
  - Résultats v1 (HathiTrust) à effacer et recalculer

## Session 2026-03-12

### MariaDB — résolution crash loop
- Cause : tc.log corrompu après chmod incorrect
- Fix : rm tc.log + redémarrage avec --tc-heuristic-recover=rollback puis restart normal
- MariaDB up : 2 479 781 titres accessibles

### Diagnostic ISFDB — structure langues et VF
- `languages` : lang_id=22 → French (code 'fre'), lang_id=17 → English
- `title_language` dans `titles` est numérique (FK vers languages.lang_id)
- VF françaises : titres avec `title_language=22 AND title_parent>0` → **37 578 titres**
- `pubs` n'a PAS de colonne pub_language — la langue vient des titles contenus
- Éditeur : `pubs.publisher_id` → JOIN `publishers.publisher_name`
- Traducteurs : `canonical_author.ca_status=3` sur le titre FR enfant
  (ca_status=1=auteur, ca_status=2=?, ca_status=3=traducteur confirmé)

### Bug 4 — Root cause confirmée dans 7_postprocess.py
La requête "Dernière VF" (section 2) n'a AUCUN filtre langue :
- Prend toutes pubs de toutes langues → MAX(pub_year) = édition EN/DE/ES récente
- has_french_vf : source à identifier dans 1_pipeline.py (probablement aussi cassé)
- Kornbluth Takeoff (title_id=3978) : zéro enfant title_language=22 → faux positif confirmé
- Twilight Zone : title_id=1454664 est lui-même en lang=22 (c'est le titre FR)
  Le titre EN parent est à identifier

### Colonnes à ajouter dans works pour fix VF
- first_vf_year, first_vf_title (nouvelles)
- last_vf_year, last_vf_title, last_vf_publisher (à recalculer correctement)
- last_vf_translator (nouvelle — ca_status=3 sur titre FR enfant)
- nb_vf_fr (nouvelle — nb d'éditions FR distinctes)

### TODO session suivante
1. Réécrire section VF de 7_postprocess.py avec filtre title_language=22
2. Identifier source de has_french_vf dans 1_pipeline.py et corriger
3. Ajouter last_vf_translator dans works + GUI
4. Corriger 8_app.py : masquer section VF si has_french_vf=0, ajouter traducteur
5. Corriger filtre awards (award_count > 0 AND awards != '')
6. Ajouter colonnes manquantes dans SELECT fiche détail (dp_fr, dp_us_source, etc.)

### 7_postprocess.py v3 final — résultats
- has_french_vf=1 : 10 868 (corrigé depuis 44 042)
- last_vf_year : 3 760
- avec traducteur : 8 846 (source : notes {{Tr|NOM}})
- Structure ISFDB confirmée : traducteur = notes.note_note {{Tr|}}, PAS canonical_author

### Scripts enrichissement critiques — lancés 2026-03-12
- 15_enrich_ia.py : Internet Archive, 42878 cibles DP EU+US sans VF, lancé en arrière-plan
- 16_enrich_goodreads.py : Goodreads scraping, 46 cibles avec awards sans VF, ~25 min
- Nouvelles colonnes : ia_identifier, ia_downloads, ia_has_text, ia_searched
- GR colonnes déjà présentes : gr_rating, gr_votes, gr_reviews_text, gr_summary
- TODO : 17_enrich_noosfere.py (œuvres avec VF + bios traducteurs)
- TODO : 18_enrich_sfe3.py (articles critiques SF Encyclopedia)
