"""
13_add_languages.py
Ajoute dans works les œuvres non-anglophones DP EU sans VF française.
Reprend la même logique que 1_pipeline.py mais sans le filtre title_language=EN.
Ajoute la colonne lang_orig si absente.

Usage : docker exec sf-dp-tools python3 /app/13_add_languages.py
"""

import sqlite3, mysql.connector, logging

# ── Config ────────────────────────────────────────────────────────────────────
SQLITE  = "/app/data/sf_dp.sqlite"
MYSQL   = dict(host="mariadb-sfdb", port=3306, user="root",
               password="isfdb", database="isfdb")

EN, FR  = 17, 22

# Langues cibles : tout sauf anglais et français
# (le français est déjà sa propre VF par définition)
EXCLUDE_LANGS = (EN, FR)

CURRENT_YEAR  = 2026
DP_EU_CUTOFF  = CURRENT_YEAR - 70   # mort avant 1956

TYPES = ("NOVEL", "COLLECTION", "OMNIBUS", "ANTHOLOGY")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Migration schéma ──────────────────────────────────────────────────────────
def migrate(conn):
    cols = {r[1] for r in conn.execute("PRAGMA table_info(works)")}
    if "lang_orig" not in cols:
        conn.execute("ALTER TABLE works ADD COLUMN lang_orig TEXT")
        log.info("Colonne lang_orig ajoutée")
    conn.commit()

# ── Requête MariaDB ───────────────────────────────────────────────────────────
QUERY = f"""
SELECT
    t.title_id,
    t.title_title                               AS title,
    a.author_canonical                          AS author,
    YEAR(t.title_copyright)                     AS year,
    t.title_ttype                               AS type,
    a.author_birthplace                         AS birthplace,
    a.author_language                           AS author_lang_id,
    YEAR(a.author_birthdate)                    AS birth_year,
    YEAR(a.author_deathdate)                    AS death_year,
    l_orig.lang_name                            AS lang_orig,
    -- VF française
    COUNT(DISTINCT CASE WHEN vt.title_language={FR}
          THEN vt.title_id END)                 AS has_french_vf,
    MAX(CASE WHEN vt.title_language={FR}
        THEN vt.title_title END)                AS french_title,
    -- Toutes les langues de traduction
    GROUP_CONCAT(DISTINCT CASE WHEN vt.title_language NOT IN ({EN},{FR})
          THEN l.lang_name END
          ORDER BY l.lang_name SEPARATOR ', ')  AS langues_vf,
    COUNT(DISTINCT CASE WHEN vt.title_language NOT IN ({EN},{FR})
          THEN vt.title_language END)           AS nb_langues_vf,
    COUNT(DISTINCT vt.title_id)                 AS nb_editions,
    t.title_wikipedia                           AS wikipedia_url,
    t.title_annualviews                         AS annualviews,
    t.title_seriesnum                           AS series_num
FROM titles t
LEFT JOIN canonical_author ca   ON ca.title_id    = t.title_id
LEFT JOIN authors a             ON a.author_id     = ca.author_id
LEFT JOIN languages l_orig      ON l_orig.lang_id  = t.title_language
-- variantes (traductions)
LEFT JOIN titles vt             ON vt.title_parent = t.title_id
LEFT JOIN languages l           ON l.lang_id       = vt.title_language
WHERE t.title_ttype IN {TYPES}
  AND t.title_language NOT IN ({EN}, {FR})
  AND a.author_language = t.title_language
  AND t.title_parent = 0
  AND YEAR(a.author_deathdate) > 0
  AND YEAR(a.author_deathdate) < {DP_EU_CUTOFF}
GROUP BY t.title_id
HAVING has_french_vf = 0
ORDER BY t.title_id
"""

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    # Connexion MariaDB
    my = mysql.connector.connect(**MYSQL)
    cur = my.cursor(dictionary=True)

    log.info("Requête MariaDB en cours…")
    cur.execute(QUERY)
    rows = cur.fetchall()
    log.info(f"{len(rows)} œuvres non-anglophones DP EU sans VF FR trouvées")
    my.close()

    # Connexion SQLite
    conn = sqlite3.connect(SQLITE)
    migrate(conn)

    # IDs déjà présents
    existing = {r[0] for r in conn.execute("SELECT title_id FROM works")}
    log.info(f"works actuel : {len(existing)} entrées")

    inserted = 0
    skipped  = 0

    for r in rows:
        if r["title_id"] in existing:
            skipped += 1
            continue

        # Calcul dp_eu
        dy = r["death_year"] or 0
        dp_eu = 1 if dy > 0 and dy < DP_EU_CUTOFF else 0

        conn.execute("""
            INSERT OR IGNORE INTO works (
                title_id, title, author, year, "type",
                birthplace, author_lang_id, birth_year, death_year,
                lang_orig,
                has_french_vf, french_title,
                langues_vf, nb_langues_vf, nb_editions,
                wikipedia_url, annualviews, series_num,
                dp_eu, dp_us,
                wp_searched, ol_searched, gr_searched,
                guardian_searched, ia_searched, dp_checked
            ) VALUES (
                :title_id, :title, :author, :year, :type,
                :birthplace, :author_lang_id, :birth_year, :death_year,
                :lang_orig,
                :has_french_vf, :french_title,
                :langues_vf, :nb_langues_vf, :nb_editions,
                :wikipedia_url, :annualviews, :series_num,
                :dp_eu, 0,
                0, 0, 0, 0, 0, 0
            )
        """, {**r, "dp_eu": dp_eu})
        inserted += 1

    conn.commit()

    # Stats par langue
    log.info("\n── Répartition par langue ──")
    stats = conn.execute("""
        SELECT lang_orig, COUNT(*) as nb
        FROM works
        WHERE lang_orig IS NOT NULL
        GROUP BY lang_orig
        ORDER BY nb DESC
        LIMIT 20
    """).fetchall()
    for lang, nb in stats:
        log.info(f"  {lang:<20} {nb}")

    total = conn.execute("SELECT COUNT(*) FROM works").fetchone()[0]
    log.info(f"\n✅ DONE — {inserted} insérés, {skipped} déjà présents")
    log.info(f"   Total works : {total}")
    conn.close()

if __name__ == "__main__":
    main()
