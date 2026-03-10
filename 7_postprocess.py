import mysql.connector, sqlite_utils
from collections import defaultdict

cn  = mysql.connector.connect(host='mariadb-sfdb', port=3306,
                               user='root', password='isfdb', database='isfdb')
cur = cn.cursor(dictionary=True)
db  = sqlite_utils.Database('/app/data/sf_dp.sqlite')

for col in ['nb_editions', 'first_pub_year', 'last_vf_year',
            'last_vf_publisher', 'last_vf_title']:
    try:
        db.execute('ALTER TABLE works ADD COLUMN ' + col + ' TEXT')
    except Exception:
        pass

# ── 1. Nb éditions + première publication ────────────────────────────────────
print('1. Editions...')
cur.execute("""
    SELECT pc.title_id,
           COUNT(DISTINCT pc.pub_id) as nb_ed,
           MIN(p.pub_year) as first_year
    FROM pub_content pc
    JOIN pubs p ON pc.pub_id = p.pub_id
    WHERE p.pub_ptype IN ('hc','pb','tp','ebook')
    GROUP BY pc.title_id
""")
ed_map = {r['title_id']: (r['nb_ed'], r['first_year']) for r in cur.fetchall()}
print('   ' + str(len(ed_map)) + ' titres')

# ── 2. Dernière édition VF française ────────────────────────────────────────
print('2. Dernière VF...')
cur.execute("""
    SELECT pc.title_id,
           MAX(p.pub_year) as last_year,
           pub.publisher_name,
           tp.trans_pub_title
    FROM pub_content pc
    JOIN pubs p           ON pc.pub_id       = p.pub_id
    JOIN publishers pub   ON p.publisher_id  = pub.publisher_id
    LEFT JOIN trans_pubs tp ON p.pub_id      = tp.pub_id
    WHERE p.pub_year IS NOT NULL
    GROUP BY pc.title_id
    HAVING last_year IS NOT NULL
""")
vf_map = {}
for r in cur.fetchall():
    tid = r['title_id']
    if tid not in vf_map or (r['last_year'] and r['last_year'] > vf_map[tid][0]):
        vf_map[tid] = (r['last_year'], r['publisher_name'], r['trans_pub_title'])
print('   ' + str(len(vf_map)) + ' titres')

# ── 3. Mise à jour SQLite ────────────────────────────────────────────────────
works = list(db.execute('SELECT title_id FROM works').fetchall())
updates = []
for (tid,) in works:
    ed  = ed_map.get(tid, (None, None))
    vf  = vf_map.get(tid, (None, None, None))
    updates.append({
        'title_id':        tid,
        'nb_editions':     ed[0],
        'first_pub_year':  str(ed[1].year) if ed[1] else None,
        'last_vf_year':    str(vf[0].year) if vf[0] else None,
        'last_vf_publisher': vf[1],
        'last_vf_title':   vf[2],
    })

print('Ecriture...')
db['works'].upsert_all(updates, pk='title_id')
print('OK')

print('Avec nb_editions :', db.execute(
    'SELECT COUNT(*) FROM works WHERE nb_editions > 0').fetchone()[0])
print('Avec last_vf_year:', db.execute(
    'SELECT COUNT(*) FROM works WHERE last_vf_year IS NOT NULL').fetchone()[0])

cn.close()
