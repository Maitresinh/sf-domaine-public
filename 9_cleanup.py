"""
9_cleanup.py v2
- Fix User-Agent Wikipedia
- Fix synopsis_source (ADD COLUMN si absent)
- Awards reconstruits depuis MariaDB
"""
import sqlite3, html, re, requests, time
import mysql.connector

DB = '/app/data/sf_dp.sqlite'
conn = sqlite3.connect(DB)
cur  = conn.cursor()

HEADERS = {'User-Agent': 'sf-domaine-public/1.0 (research; contact@localhost)'}

# ─────────────────────────────────────────────────────────────
# 0. MIGRATIONS SCHEMA
# ─────────────────────────────────────────────────────────────
print("=== 0. Migrations schema ===")
for col, defn in [('synopsis_source', "TEXT DEFAULT 'isfdb'")]:
    try:
        cur.execute(f'ALTER TABLE works ADD COLUMN {col} {defn}')
        conn.commit()
        print(f"  ✅ Colonne {col} ajoutée")
    except Exception:
        print(f"  (colonne {col} déjà présente)")

# Marquer les synopsis existants comme isfdb
cur.execute("UPDATE works SET synopsis_source='isfdb' WHERE synopsis IS NOT NULL AND synopsis_source IS NULL")
conn.commit()

# ─────────────────────────────────────────────────────────────
# 1. NETTOYAGE HTML ENTITIES
# ─────────────────────────────────────────────────────────────
print("\n=== 1. Nettoyage HTML entities ===")
for col in ['author', 'title', 'french_title', 'awards', 'synopsis']:
    cur.execute(f"""
        SELECT title_id, {col} FROM works
        WHERE {col} LIKE '%&#%' OR {col} LIKE '%&amp;%' OR {col} LIKE '%&quot;%'
    """)
    rows = cur.fetchall()
    print(f"  {col} : {len(rows)} lignes")
    for tid, val in rows:
        if val:
            cleaned = html.unescape(str(val))
            if cleaned != val:
                cur.execute(f"UPDATE works SET {col}=? WHERE title_id=?", (cleaned, tid))
conn.commit()
print("  ✅ HTML entities nettoyés")

# ─────────────────────────────────────────────────────────────
# 2. RECONSTRUCTION AWARDS DEPUIS MARIADB
# ─────────────────────────────────────────────────────────────
print("\n=== 2. Reconstruction awards manquants ===")

cur.execute("""
    SELECT title_id FROM works
    WHERE award_count > 0 AND (awards IS NULL OR awards = '')
""")
missing_ids = [r[0] for r in cur.fetchall()]
print(f"  {len(missing_ids)} œuvres avec award_count > 0 mais awards vide")

try:
    isf = mysql.connector.connect(
        host='mariadb-sfdb', port=3306,
        user='root', password='root', database='isfdb'
    )
    ic = isf.cursor()
    rebuilt = 0

    for tid in missing_ids:
        ic.execute("""
            SELECT at.award_type_name, ac.award_cat_name,
                   ta.award_level, ta.award_year
            FROM title_awards ta
            JOIN award_cats ac ON ta.award_cat_id = ac.award_cat_id
            JOIN award_types at ON ac.award_cat_type_id = at.award_type_id
            WHERE ta.title_id = %s AND ta.award_level BETWEEN 1 AND 8
            ORDER BY ta.award_level, ta.award_year
        """, (tid,))
        rows = ic.fetchall()
        if not rows:
            continue
        parts = []
        for atype, acat, level, ayear in rows:
            emoji = '🏆' if level == 1 else '🏅'
            parts.append(f"{emoji} {atype} – {acat} ({ayear})")
        awards_txt = ' | '.join(parts)
        cur.execute("UPDATE works SET awards=? WHERE title_id=?", (awards_txt, tid))
        rebuilt += 1

    conn.commit()
    isf.close()
    print(f"  ✅ {rebuilt} œuvres reconstruites")

except Exception as e:
    print(f"  ❌ MariaDB inaccessible : {e}")

# Vérification
cur.execute("""
    SELECT COUNT(*) FROM works
    WHERE (dp_eu=1 OR dp_us=1) AND has_french_vf=0
    AND awards IS NOT NULL AND awards != ''
""")
print(f"  Awards texte non vide (DP sans VF) après fix : {cur.fetchone()[0]}")

# ─────────────────────────────────────────────────────────────
# 3. ENRICHISSEMENT WIKIPEDIA INTRO COMPLÈTE
# ─────────────────────────────────────────────────────────────
print("\n=== 3. Enrichissement Wikipedia intro complète ===")

cur.execute("""
    SELECT title_id, title, author, wikipedia_url
    FROM works
    WHERE (dp_eu=1 OR dp_us=1)
    AND has_french_vf=0
    AND wikipedia_url IS NOT NULL AND wikipedia_url != ''
    AND (synopsis IS NULL OR length(synopsis) < 300)
    ORDER BY annualviews DESC NULLS LAST
    LIMIT 500
""")
rows = cur.fetchall()
print(f"  {len(rows)} œuvres ciblées")

updated = errors = 0
for tid, title, author, wp_url in rows:
    slug = wp_url.rstrip('/').split('/')[-1]
    try:
        r = requests.get(
            'https://en.wikipedia.org/w/api.php',
            params={
                'action':      'query',
                'titles':      slug.replace('_', ' '),
                'prop':        'extracts',
                'exintro':     True,
                'explaintext': True,
                'redirects':   True,
                'format':      'json',
            },
            headers=HEADERS,
            timeout=10
        )
        data  = r.json()
        pages = data.get('query', {}).get('pages', {})
        page  = next(iter(pages.values()))

        if page.get('pageid', -1) == -1:
            continue

        extract = page.get('extract', '').strip()
        extract = re.sub(r'\n{3,}', '\n\n', extract)

        if extract and len(extract) > 200:
            cur.execute("""
                UPDATE works SET synopsis=?, synopsis_source='wikipedia_full'
                WHERE title_id=?
            """, (extract[:2000], tid))
            updated += 1
            if updated % 50 == 0:
                conn.commit()
                print(f"  ... {updated} mis à jour")

        time.sleep(0.25)

    except Exception as e:
        errors += 1
        if errors <= 3:
            print(f"  Erreur [{tid}] {title}: {e}")

conn.commit()
print(f"  ✅ {updated} synopsis enrichis, {errors} erreurs")

# ─────────────────────────────────────────────────────────────
# 4. STATS FINALES
# ─────────────────────────────────────────────────────────────
print("\n=== 4. Stats finales ===")
for label, sql in [
    ("Total DP sans VF",                "SELECT COUNT(*) FROM works WHERE (dp_eu=1 OR dp_us=1) AND has_french_vf=0"),
    ("Synopsis total",                  "SELECT COUNT(*) FROM works WHERE synopsis IS NOT NULL AND synopsis!=''"),
    ("Synopsis isfdb",                  "SELECT COUNT(*) FROM works WHERE synopsis_source='isfdb'"),
    ("Synopsis wikipedia_full",         "SELECT COUNT(*) FROM works WHERE synopsis_source='wikipedia_full'"),
    ("Awards texte non vide (tout DP)", "SELECT COUNT(*) FROM works WHERE (dp_eu=1 OR dp_us=1) AND awards IS NOT NULL AND awards!=''"),
    ("award_count>0 DP sans VF",        "SELECT COUNT(*) FROM works WHERE (dp_eu=1 OR dp_us=1) AND has_french_vf=0 AND award_count>0"),
    ("HTML entities restants",          "SELECT COUNT(*) FROM works WHERE author LIKE '%&#%' OR title LIKE '%&#%'"),
]:
    cur.execute(sql)
    print(f"  {label:45s}: {cur.fetchone()[0]}")

conn.close()
print("\n✅ 9_cleanup.py terminé")
