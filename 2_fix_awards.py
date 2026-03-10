import mysql.connector, sqlite_utils
from collections import defaultdict

cn  = mysql.connector.connect(host='mariadb-sfdb', port=3306,
                               user='root', password='isfdb', database='isfdb')
cur = cn.cursor(dictionary=True)
db  = sqlite_utils.Database('/app/data/sf_dp.sqlite')

cur.execute("""
    SELECT a.award_title, a.award_author, a.award_level,
           at2.award_type_name, ac.award_cat_name
    FROM awards a
    JOIN award_cats  ac  ON a.award_cat_id      = ac.award_cat_id
    JOIN award_types at2 ON ac.award_cat_type_id = at2.award_type_id
    WHERE a.award_level IN (1, 2)
      AND a.award_title  IS NOT NULL AND a.award_title  != ''
      AND a.award_author IS NOT NULL AND a.award_author != ''
""")
raw = cur.fetchall()
print(str(len(raw)) + ' entrees awards')

awards_by_key = defaultdict(list)
for row in raw:
    key = (row['award_title'].lower().strip(), row['award_author'].lower().strip())
    awards_by_key[key].append(row)

works = list(db.execute('SELECT title_id, title, author, year FROM works').fetchall())
updates, updated, cleared = [], 0, 0

for i, (title_id, title, author, year) in enumerate(works):
    if i % 10000 == 0:
        print(str(i) + '/' + str(len(works)))
    key = (title.lower().strip(), author.lower().strip() if author else '')
    matches = awards_by_key.get(key, [])
    parts = [('🏆' if a['award_level']=='1' else '🏅') + a['award_type_name'] + ' - ' + a['award_cat_name']
             for a in matches]
    new_awards = ' | '.join(parts) if parts else None
    updates.append({'title_id': title_id, 'awards': new_awards, 'award_count': len(matches)})
    if new_awards:
        updated += 1
    else:
        cleared += 1

print('Ecriture ' + str(len(updates)) + ' lignes...')
db['works'].upsert_all(updates, pk='title_id')
print('OK ' + str(updated) + ' avec awards, ' + str(cleared) + ' nettoyes')

print('Romans US 1940-1963 primes DP EU sans VF')
for r in db.execute("""
    SELECT title, author, year, dp_us, award_count, awards FROM works
    WHERE type='novel' AND dp_eu=1 AND has_french_vf=0
      AND year BETWEEN 1940 AND 1963 AND award_count > 0
    ORDER BY award_count DESC, year ASC
""").fetchall():
    print(r)

cn.close()
