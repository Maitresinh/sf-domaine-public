"""
25_contents_json.py
Pré-calcule le contenu des anthologies et collections dans contents_json.
Cibles : works WHERE type IN (anthology, collection, omnibus)
         AND dp_eu=1 AND dp_us=1

Format JSON :
[
  {"title_id": 123, "title": "...", "year": 1930, "type": "SHORTFICTION",
   "has_vf": 0, "dp_eu": 1, "dp_us": 1},
  ...
]
"""
import fcntl, sys
_lf = open("/app/data/25.lock", "w")
try:
    fcntl.flock(_lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
except IOError:
    print("Instance deja en cours. Abandon."); sys.exit(0)

import sqlite3, json, logging
import mysql.connector
from datetime import datetime

DB       = '/app/data/sf_dp.sqlite'
LOG_FILE = '/app/data/25_contents.log'
COMMIT_N = 100
BATCH    = 500

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()])
log = logging.getLogger()
log.info('=== 25_contents_json.py ===')

sc = sqlite3.connect(DB, timeout=60)
sc.row_factory = sqlite3.Row

mc = mysql.connector.connect(
    host='mariadb-sfdb', port=3306,
    user='root', password='isfdb', database='isfdb',
    connection_timeout=15)
cur = mc.cursor(dictionary=True)

# Colonne contents_json
try:
    sc.execute('ALTER TABLE works ADD COLUMN contents_json TEXT')
    sc.commit()
    log.info('  Colonne contents_json creee')
except Exception:
    log.info('  Colonne contents_json deja presente')

# Cibles
rows = sc.execute("""
    SELECT w.title_id, w.title, w.author, w.year
    FROM works w
    WHERE "type" IN ('anthology','collection','omnibus')
    AND (dp_eu=1 OR dp_us=1)
    AND contents_json IS NULL
    ORDER BY annualviews DESC NULLS LAST
""").fetchall()
targets = [(r['title_id'], r['title'], r['author'], r['year']) for r in rows]
log.info(f'  {len(targets)} anthologies/collections a traiter')

# Index DP et VF depuis SQLite pour enrichir chaque nouvelle
log.info('  Chargement index DP+VF SQLite...')
dp_index = {}
for r in sc.execute("""
    SELECT title_id, dp_eu, dp_us, has_french_vf
    FROM works
""").fetchall():
    dp_index[r['title_id']] = (r['dp_eu'], r['dp_us'], r['has_french_vf'])
log.info(f'  {len(dp_index)} titres indexes')

n_done = n_found = n_empty = 0

for i in range(0, len(targets), BATCH):
    batch = targets[i:i+BATCH]
    ids   = [t[0] for t in batch]
    ph    = ','.join(['%s'] * len(ids))

    cur.execute(f"""
        SELECT DISTINCT
            pc1.title_id    AS parent_id,
            t2.title_id     AS child_id,
            t2.title_title  AS title,
            t2.title_ttype  AS ttype,
            YEAR(t2.title_copyright) AS yr
        FROM pub_content pc1
        JOIN pub_content pc2 ON pc1.pub_id = pc2.pub_id
        JOIN titles t2 ON pc2.title_id = t2.title_id
        WHERE pc1.title_id IN ({ph})
          AND t2.title_ttype IN ('SHORTFICTION','NOVELETTE','NOVELLA','NOVEL')
          AND t2.title_id != pc1.title_id
        ORDER BY pc1.title_id, yr, t2.title_title
    """, ids)

    # Grouper par parent
    contents = {}
    for r in cur.fetchall():
        pid = r['parent_id']
        if pid not in contents:
            contents[pid] = []
        cid = r['child_id']
        dp_eu, dp_us, has_vf = dp_index.get(cid, (None, None, 0))
        entry = {
            'title_id': cid,
            'title':    r['title'],
            'year':     r['yr'],
            'type':     r['ttype'],
            'dp_eu':    dp_eu,
            'dp_us':    dp_us,
            'has_vf':   has_vf or 0,
        }
        # Eviter doublons
        if not any(e['title_id'] == cid for e in contents[pid]):
            contents[pid].append(entry)

    # Ecrire dans SQLite
    for tid, title, author, year in batch:
        if tid in contents and contents[tid]:
            j = json.dumps(contents[tid], ensure_ascii=False, separators=(',',':'))
            sc.execute('UPDATE works SET contents_json=? WHERE title_id=?', (j, tid))
            n_found += 1
            if n_found <= 10 or n_found % 100 == 0:
                log.info(f'  {author} — {title} ({year}) : {len(contents[tid])} nouvelles')
        else:
            sc.execute("UPDATE works SET contents_json='[]' WHERE title_id=?", (tid,))
            n_empty += 1
        n_done += 1

    if n_done % COMMIT_N == 0:
        sc.commit()
        log.info(f'  CHECKPOINT {n_done}/{len(targets)} — trouvees:{n_found} vides:{n_empty}')

sc.commit()
log.info('=== RESULTATS ===')
for label, sql in [
    ('contents_json renseigné', "SELECT COUNT(*) FROM works WHERE contents_json IS NOT NULL"),
    ('avec contenu',            "SELECT COUNT(*) FROM works WHERE contents_json IS NOT NULL AND contents_json != '[]'"),
    ('vides',                   "SELECT COUNT(*) FROM works WHERE contents_json = '[]'"),
]:
    log.info(f'  {label:35s}: {sc.execute(sql).fetchone()[0]}')

log.info(f'TERMINE {datetime.now().strftime("%H:%M:%S")} — {n_found} trouvees / {n_empty} vides')
sc.close(); mc.close(); _lf.close()
