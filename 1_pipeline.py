import mysql.connector
import sqlite_utils
import pandas as pd
import requests
import time
from datetime import date

MYSQL     = dict(host="mariadb-sfdb", port=3306,
                 user="root", password="isfdb", database="isfdb")
SQLITE    = "/app/data/sf_dp.sqlite"
CCE_DIR   = "/app/data/cce-spreadsheets"
DP_CUTOFF = date.today().year - 70
EN, FR    = 17, 22

print("Connexion MariaDB...")
my  = mysql.connector.connect(**MYSQL)
cur = my.cursor(dictionary=True)

# ── CCE ───────────────────────────────────────────────────────────────────────
print("Chargement CCE...")
not_renewed = pd.read_csv(f"{CCE_DIR}/FINAL-not-renewed.tsv", sep="\t",
                          usecols=["title","author"], low_memory=False)
renewed     = pd.read_csv(f"{CCE_DIR}/FINAL-renewed.tsv", sep="\t",
                          usecols=["title","author"], low_memory=False)
not_renewed["_norm"] = not_renewed["title"].astype(str).str.lower().str.strip()
renewed["_norm"]     = renewed["title"].astype(str).str.lower().str.strip()
print(f"CCE : {len(not_renewed)} non renouvelés / {len(renewed)} renouvelés")

renewed_set     = set(renewed["_norm"].dropna())
not_renewed_set = set(not_renewed["_norm"].dropna())

def us_copyright(title, year):
    if not year: return None, "année inconnue"
    y = int(year)
    if y < 1928: return True,  "publié avant 1928"
    if y > 1963: return False, "publié après 1963"
    norm = title.lower().strip()
    if norm in renewed_set:
        return False, "copyright renouvelé (CCE)"
    if norm in not_renewed_set:
        return True,  "non renouvelé (CCE)"
    return None, "non trouvé dans CCE (1928-1963)"

# ── Wikidata ──────────────────────────────────────────────────────────────────
_wd = {}
def wikidata_death(name):
    if name in _wd: return _wd[name]
    sparql = f'SELECT ?d WHERE {{ ?p wdt:P31 wd:Q5 ; rdfs:label "{name}"@en ; wdt:P570 ?d }} LIMIT 1'
    try:
        r = requests.get("https://query.wikidata.org/sparql",
                         params={"query": sparql, "format": "json"},
                         headers={"User-Agent": "sf-dp/1.0"}, timeout=8)
        b = r.json()["results"]["bindings"]
        result = b[0]["d"]["value"][:4] if b else None
    except Exception:
        result = None
    _wd[name] = result
    time.sleep(0.3)
    return result

# ── Awards : chargement complet en mémoire ────────────────────────────────────
print("Chargement awards ISFDB...")
cur.execute("""
    SELECT aw.award_title, aw.award_author, aw.award_level,
           YEAR(aw.award_year) AS award_year,
           at.award_type_name, ac.award_cat_name
    FROM awards aw
    JOIN award_types at  ON at.award_type_id = aw.award_type_id
    LEFT JOIN award_cats ac ON ac.award_cat_id = aw.award_cat_id
    WHERE aw.award_level IN (1, 2)
""")
awards_raw = cur.fetchall()
# Index par titre normalisé
awards_idx = {}
for a in awards_raw:
    norm = (a["award_title"] or "").lower().strip()
    if norm not in awards_idx:
        awards_idx[norm] = []
    awards_idx[norm].append(a)
print(f"{len(awards_raw)} awards winner/nominee indexés")

def get_awards(title):
    norm = title.lower().strip()
    hits = awards_idx.get(norm, [])
    if not hits: return "", 0
    labels = []
    for h in hits:
        level = "🏆" if h["award_level"] == 1 else "🏅"
        labels.append(f"{level}{h['award_type_name']} {h['award_year']}"
                      f"{' – ' + h['award_cat_name'] if h['award_cat_name'] else ''}")
    return " | ".join(labels), len(hits)

def readable_type(ttype, storylen):
    return storylen if ttype == "SHORTFICTION" and storylen else ttype.lower()

# ── Requête principale ────────────────────────────────────────────────────────
QUERY = f"""
SELECT
    t.title_id,
    t.title_title                               AS title,
    YEAR(t.title_copyright)                     AS year,
    t.title_ttype                               AS ttype,
    t.title_storylen                            AS storylen,
    a.author_canonical                          AS author,
    LEFT(a.author_birthdate, 4)                 AS birth_year,
    LEFT(a.author_deathdate, 4)                 AS death_year,
    a.author_birthplace AS birthplace, a.author_language AS author_lang_id,
    -- Série
    s.series_title                              AS series,
    t.title_seriesnum                           AS series_num,
    -- VF française
    COUNT(DISTINCT CASE WHEN vt.title_language={FR}
          THEN t.title_id END)                  AS has_french_vf,
    MAX(CASE WHEN vt.title_language={FR}
          THEN vt.title_title END)              AS french_title,
    -- Toutes les langues de traduction
    GROUP_CONCAT(DISTINCT CASE WHEN vt.title_language != {EN}
          THEN l.lang_name END
          ORDER BY l.lang_name SEPARATOR ', ')  AS langues_vf,
    COUNT(DISTINCT CASE WHEN vt.title_language != {EN}
          THEN vt.title_language END)           AS nb_langues_vf,
    -- Nombre d'éditions
    0 AS nb_editions
FROM titles t
JOIN canonical_author ca ON ca.title_id = t.title_id AND ca.ca_status = 1
JOIN authors a            ON a.author_id = ca.author_id
LEFT JOIN series s        ON s.series_id = t.series_id
LEFT JOIN titles vt       ON vt.title_parent = t.title_id
LEFT JOIN languages l     ON l.lang_id = vt.title_language

WHERE
    t.title_parent = 0
    AND t.title_language = {EN}
    AND t.title_ttype IN ('NOVEL','SHORTFICTION','COLLECTION','ANTHOLOGY','CHAPBOOK')
    AND (t.title_non_genre IS NULL OR t.title_non_genre = 'No')
    AND (t.title_graphic   IS NULL OR t.title_graphic   = 'No')
    AND t.title_title NOT REGEXP '[(\\[]excerpt|abridg|extract|play|adapt|part [0-9]'
    AND YEAR(t.title_copyright) > 0
    AND YEAR(t.title_copyright) <= YEAR(a.author_deathdate) + 2
GROUP BY
    t.title_id, t.title_title, t.title_copyright, t.title_ttype, t.title_storylen,
    a.author_canonical, a.author_birthdate, a.author_deathdate, a.author_birthplace,
    s.series_title, t.title_seriesnum
ORDER BY YEAR(t.title_copyright)
"""

print("Requête ISFDB (5-10 min sur tout le catalogue)...")
cur.execute(QUERY)
rows = cur.fetchall()
print(f"{len(rows)} œuvres trouvées")

# ── Pipeline ──────────────────────────────────────────────────────────────────
results = []
for i, w in enumerate(rows, 1):
    w["type"] = readable_type(w["ttype"], w["storylen"])

    # DP Europe
    dy = w.get("death_year")
    if not dy:
        dy = wikidata_death(w["author"])
        if dy: print(f"  Wikidata → {w['author']} †{dy}")
    w["death_year"] = dy
    w["dp_eu"] = bool(dy and int(dy) < DP_CUTOFF)

    # DP USA
    w["dp_us"], w["dp_us_reason"] = us_copyright(w["title"], w.get("year"))

    # Awards
    w["awards"], w["award_count"] = get_awards(w["title"])

    # URL
    w["isfdb_url"] = f"https://www.isfdb.org/cgi-bin/title.cgi?{w['title_id']}"

    results.append(w)
    if i % 1000 == 0:
        print(f"  {i}/{len(rows)}...")

print(f"{len(results)} œuvres traitées")

# ── SQLite ────────────────────────────────────────────────────────────────────
db = sqlite_utils.Database(SQLITE)
KEEP = ["title_id","title","author","year","type","birthplace", "author_lang_id",
        "birth_year","death_year","dp_eu","dp_us","dp_us_reason",
        "has_french_vf","french_title","series","series_num",
        "langues_vf","nb_langues_vf","nb_editions",
        "awards","award_count","isfdb_url"]

db["works"].drop(ignore=True)
db["works"].insert_all([{k: r.get(k) for k in KEEP} for r in results], pk="title_id", replace=True)
for col in ["year","dp_eu","dp_us","has_french_vf","author","type","series"]:
    db["works"].create_index([col], if_not_exists=True)
db["works"].disable_fts()
db["works"].enable_fts(["title","author","series"], create_triggers=True)

if "editorial" not in db.table_names():
    db["editorial"].create({
        "title_id": int, "status": str, "note": str,
        "ai_note": str,  "updated_at": str,
    }, pk="title_id")

print(f"✅ {db['works'].count} œuvres dans {SQLITE}")
