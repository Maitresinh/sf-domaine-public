"""
11_fix_awards_full.py
Reconstruction complète du texte awards pour les 2019 œuvres
avec award_count > 0 mais champ awards vide.

Lancer :
  docker exec sf-dp-tools python /app/11_fix_awards_full.py
"""
import sqlite3, mysql.connector, logging

DB = '/app/data/sf_dp.sqlite'
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
log = logging.getLogger()

conn = sqlite3.connect(DB)
cur  = conn.cursor()

# ── Connexion MariaDB ──────────────────────────────────────────────────────────
try:
    isf = mysql.connector.connect(
        host='mariadb-sfdb', port=3306,
        user='root', password='isfdb', database='isfdb'
    )
    ic = isf.cursor()
    log.info("✅ MariaDB connecté")
except Exception as e:
    log.error(f"❌ MariaDB inaccessible : {e}")
    exit(1)

# ── Œuvres à corriger ─────────────────────────────────────────────────────────
cur.execute("""
    SELECT title_id, title, author FROM works
    WHERE award_count > 0 AND (awards IS NULL OR awards = '')
    ORDER BY title_id
""")
missing = cur.fetchall()
log.info(f"{len(missing)} œuvres à reconstruire")

# ── Reconstruction ─────────────────────────────────────────────────────────────
rebuilt = empty = errors = 0

for title_id, title, author in missing:
    try:
        ic.execute("""
            SELECT
                at.award_type_name,
                ac.award_cat_name,
                CAST(a.award_level AS UNSIGNED) as level,
                a.award_year
            FROM title_awards ta
            JOIN awards      a  ON ta.award_id         = a.award_id
            JOIN award_cats  ac ON a.award_cat_id       = ac.award_cat_id
            JOIN award_types at ON ac.award_cat_type_id = at.award_type_id
            WHERE ta.title_id = %s
            AND   CAST(a.award_level AS UNSIGNED) BETWEEN 1 AND 8
            ORDER BY CAST(a.award_level AS UNSIGNED) ASC, a.award_year ASC
        """, (title_id,))
        rows = ic.fetchall()
        year_s = str(rows[0][3])[:4] if rows and rows[0][3] else '?'
        if not rows:
            # award_count=1 mais aucun niveau 1-8 → probablement niveau 9+ (éligible)
            # On remet award_count à 0 pour ne pas polluer les filtres
            cur.execute("UPDATE works SET award_count=0 WHERE title_id=?", (title_id,))
            empty += 1
            continue

        parts = []
        for atype, acat, level, ayear in rows:
            if level == 1:
                emoji = '🏆'
            elif level <= 8:
                emoji = '🏅'
            else:
                continue
            year_s = str(ayear)[:4] if ayear else '?'
            parts.append(f"{emoji} {atype} – {acat} ({year_s})")

        if parts:
            awards_txt = ' | '.join(parts)
            cur.execute(
                "UPDATE works SET awards=? WHERE title_id=?",
                (awards_txt, title_id)
            )
            rebuilt += 1
        else:
            cur.execute("UPDATE works SET award_count=0 WHERE title_id=?", (title_id,))
            empty += 1

        if (rebuilt + empty) % 200 == 0:
            conn.commit()
            log.info(f"  ... {rebuilt} reconstruits, {empty} vidés")

    except Exception as e:
        errors += 1
        if errors <= 5:
            log.warning(f"  Erreur [{title_id}] {title}: {e}")

conn.commit()
isf.close()
log.info(f"\n✅ Résultat : {rebuilt} reconstruits, {empty} award_count remis à 0, {errors} erreurs")

# ── Vérification ───────────────────────────────────────────────────────────────
log.info("\n=== Vérification ===")
for label, sql in [
    ("award_count > 0 total",                "SELECT COUNT(*) FROM works WHERE award_count > 0"),
    ("awards texte non vide",                "SELECT COUNT(*) FROM works WHERE awards IS NOT NULL AND awards != ''"),
    ("award_count>0 MAIS awards vide",       "SELECT COUNT(*) FROM works WHERE award_count>0 AND (awards IS NULL OR awards='')"),
    ("DP sans VF avec awards",               "SELECT COUNT(*) FROM works WHERE (dp_eu=1 OR dp_us=1) AND has_french_vf=0 AND award_count>0"),
    ("DP sans VF victoires (🏆)",            "SELECT COUNT(*) FROM works WHERE (dp_eu=1 OR dp_us=1) AND has_french_vf=0 AND awards LIKE '%🏆%'"),
    ("DP sans VF nominations (🏅)",          "SELECT COUNT(*) FROM works WHERE (dp_eu=1 OR dp_us=1) AND has_french_vf=0 AND awards LIKE '%🏅%'"),
]:
    cur.execute(sql)
    log.info(f"  {label:45s}: {cur.fetchone()[0]}")

# Top 10 primés DP sans VF
log.info("\n  Top 10 primés DP sans VF :")
cur.execute("""
    SELECT title, author, year, award_count, awards FROM works
    WHERE (dp_eu=1 OR dp_us=1) AND has_french_vf=0
    AND awards IS NOT NULL AND awards != ''
    ORDER BY award_count DESC, annualviews DESC NULLS LAST
    LIMIT 10
""")
for row in cur.fetchall():
    log.info(f"  [{row[2]}] {row[1]} — {row[0]} | {row[4][:80]}")

conn.close()
log.info("\n✅ 11_fix_awards_full.py terminé")
