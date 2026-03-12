
import mysql.connector, sqlite_utils

cn  = mysql.connector.connect(host='mariadb-sfdb', port=3306,
                               user='root', password='isfdb', database='isfdb')
cur = cn.cursor(dictionary=True)
db  = sqlite_utils.Database('/app/data/sf_dp.sqlite')

for col in ['first_vf_year','first_vf_title','last_vf_translator','nb_vf_fr']:
    try:
        db.execute('ALTER TABLE works ADD COLUMN ' + col + ' TEXT')
    except Exception:
        pass

print('1. Editions...')
cur.execute('''
    SELECT pc.title_id,
           COUNT(DISTINCT pc.pub_id) AS nb_ed,
           MIN(p.pub_year)           AS first_year
    FROM pub_content pc
    JOIN pubs p ON pc.pub_id = p.pub_id
    WHERE p.pub_ptype IN ('hc','pb','tp','ebook')
    GROUP BY pc.title_id
''')
ed_map = {r['title_id']: (r['nb_ed'], r['first_year']) for r in cur.fetchall()}
print('   ' + str(len(ed_map)) + ' titres')

print('2. VF francaises (title_language=22)...')
cur.execute('''
    SELECT
        t.title_parent AS orig_id,
        t.title_title  AS fr_title,
        MIN(p.pub_year) AS first_vf_year,
        MAX(p.pub_year) AS last_vf_year,
        COUNT(DISTINCT p.pub_id) AS nb_ed_fr,
        GROUP_CONCAT(DISTINCT pub.publisher_name ORDER BY p.pub_year DESC SEPARATOR " | ") AS editeurs,
        GROUP_CONCAT(DISTINCT a.author_canonical SEPARATOR " / ") AS traducteurs
    FROM titles t
    JOIN pub_content pc  ON pc.title_id      = t.title_id
    JOIN pubs p          ON p.pub_id         = pc.pub_id
    JOIN publishers pub  ON pub.publisher_id = p.publisher_id
    LEFT JOIN canonical_author ca ON ca.title_id = t.title_id AND ca.ca_status = 1
    LEFT JOIN authors a           ON a.author_id  = ca.author_id AND a.author_language = 22
    WHERE t.title_language = 22
      AND t.title_parent   > 0
      AND p.pub_year IS NOT NULL
    GROUP BY t.title_parent, t.title_title
''')
vf_map = {}
for r in cur.fetchall():
    oid = r['orig_id']
    if oid not in vf_map or (r['last_vf_year'] and (not vf_map[oid]['last_vf_year'] or r['last_vf_year'] > vf_map[oid]['last_vf_year'])):
        vf_map[oid] = r
print('   ' + str(len(vf_map)) + ' titres avec VF FR')

print('3. Correction has_french_vf + ecriture...')
works = list(db.execute('SELECT title_id, has_french_vf FROM works').fetchall())
updates = []
fp = 0

def yr(d):
    if d is None: return None
    try: return str(d.year) if hasattr(d, 'year') else str(d)[:4]
    except: return None

for (tid, hfv) in works:
    ed = ed_map.get(tid, (None, None))
    vf = vf_map.get(tid)
    if hfv == 1 and not vf:
        fp += 1
    last_pub = vf['editeurs'].split(' | ')[0] if vf and vf['editeurs'] else None
    updates.append({
        'title_id':           tid,
        'nb_editions':        ed[0],
        'first_pub_year':     yr(ed[1]),
        'has_french_vf':      1 if vf else 0,
        'first_vf_year':      yr(vf['first_vf_year'])  if vf else None,
        'first_vf_title':     vf['fr_title']            if vf else None,
        'last_vf_year':       yr(vf['last_vf_year'])   if vf else None,
        'last_vf_title':      vf['fr_title']            if vf else None,
        'last_vf_publisher':  last_pub,
        'last_vf_translator': vf['traducteurs']         if vf else None,
        'nb_vf_fr':           str(vf['nb_ed_fr'])       if vf else None,
    })

print('   ' + str(fp) + ' faux positifs has_french_vf corriges')
db['works'].upsert_all(updates, pk='title_id')
print('OK')

for label, q in [
    ('has_french_vf=1',       'SELECT COUNT(*) FROM works WHERE has_french_vf=1'),
    ('last_vf_year renseigne','SELECT COUNT(*) FROM works WHERE last_vf_year IS NOT NULL'),
    ('avec traducteur',       "SELECT COUNT(*) FROM works WHERE last_vf_translator IS NOT NULL AND last_vf_translator != ''"),
    ('nb_editions > 0',       'SELECT COUNT(*) FROM works WHERE nb_editions > 0'),
]:
    n = db.execute(q).fetchone()[0]
    print('   ' + label + ': ' + str(n))
cn.close()
print('Termine.')
