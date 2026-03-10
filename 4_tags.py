import mysql.connector, sqlite_utils

cn  = mysql.connector.connect(host='mariadb-sfdb', port=3306,
                               user='root', password='isfdb', database='isfdb')
cur = cn.cursor(dictionary=True)
db  = sqlite_utils.Database('/app/data/sf_dp.sqlite')

# Mots-clés qui signalent du bruit
NOISE = ['read by', 'read ', 'owned', 'wish list', 'audible', 'kindle',
         'award winner', 'award finalist', 'hugo award', 'nebula award',
         'locus award', 'campbell award', '1-award']

# Listes de référence connues (signal éditorial fort)
LISTS = ['masterwork', 'core collection', 'best novels', 'best sf',
         'best science fiction', '100 best', '50 essential', 'anatomy of wonder',
         'reading list', 'recommended']

def is_noise(tag):
    t = tag.lower()
    return any(n in t for n in NOISE)

def is_list(tag):
    t = tag.lower()
    return any(l in t for l in LISTS)

print('Chargement tags ISFDB...')
cur.execute("""
    SELECT tm.title_id, t.tag_name
    FROM tag_mapping tm
    JOIN tags t ON tm.tag_id = t.tag_id
    WHERE t.tag_status = 0
""")
rows = cur.fetchall()
print(str(len(rows)) + ' tag_mapping entrees')

# Grouper par title_id
from collections import defaultdict
tags_by_title  = defaultdict(list)
lists_by_title = defaultdict(list)

for r in rows:
    tag = r['tag_name'].strip()
    tid = r['title_id']
    if is_noise(tag):
        continue
    if is_list(tag):
        lists_by_title[tid].append(tag)
    else:
        tags_by_title[tid].append(tag)

# Ajouter colonnes si absentes
for col in ['isfdb_tags', 'isfdb_lists']:
    try:
        db.execute('ALTER TABLE works ADD COLUMN ' + col + ' TEXT')
    except Exception:
        pass

# Récupérer les title_id du SQLite
works = list(db.execute('SELECT title_id FROM works').fetchall())
print(str(len(works)) + ' oeuvres dans SQLite')

updates = []
tagged = 0
for (title_id,) in works:
    tags  = tags_by_title.get(title_id, [])
    lists = lists_by_title.get(title_id, [])
    updates.append({
        'title_id':    title_id,
        'isfdb_tags':  ', '.join(tags)  or None,
        'isfdb_lists': ', '.join(lists) or None,
    })
    if tags: tagged += 1

print('Ecriture ' + str(len(updates)) + ' lignes...')
db['works'].upsert_all(updates, pk='title_id')
print('OK — ' + str(tagged) + ' oeuvres avec tags')

# Contrôle
print('\n=== Exemples romans DP EU avec tags ===')
for r in db.execute("""
    SELECT title, author, year, isfdb_tags, isfdb_lists
    FROM works
    WHERE type='novel' AND dp_eu=1 AND has_french_vf=0
      AND isfdb_tags IS NOT NULL
    ORDER BY award_count DESC
    LIMIT 5
""").fetchall():
    print(r)

cn.close()
