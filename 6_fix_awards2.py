import mysql.connector, sqlite_utils
from collections import defaultdict

cn  = mysql.connector.connect(host='mariadb-sfdb', port=3306,
                               user='root', password='isfdb', database='isfdb')
cur = cn.cursor(dictionary=True)
db  = sqlite_utils.Database('/app/data/sf_dp.sqlite')

# Tous les awards via title_awards FK
# level 1        = victoire      🏆
# level 2-8      = nomination    🏅
# level 10-71    = classement sondage 📊
# level 9,90-99  = exclus (éligible/retiré/non-genre)
cur.execute("""
    SELECT ta.title_id, at2.award_type_name, ac.award_cat_name,
           CAST(a.award_level AS UNSIGNED) as lvl
    FROM title_awards ta
    JOIN awards a        ON ta.award_id        = a.award_id
    JOIN award_cats ac   ON a.award_cat_id     = ac.award_cat_id
    JOIN award_types at2 ON ac.award_cat_type_id = at2.award_type_id
    WHERE CAST(a.award_level AS UNSIGNED) BETWEEN 1 AND 71
""")
awards_fk = defaultdict(list)
for r in cur.fetchall():
    awards_fk[r['title_id']].append(r)

# award_titles_report pour couverture large
cur.execute('SELECT title_id, score FROM award_titles_report')
score_map = {}
for r in cur.fetchall():
    tid = r['title_id']
    if tid not in score_map or r['score'] > score_map[tid]:
        score_map[tid] = r['score']

print('FK awards: ' + str(len(awards_fk)))
print('Score map: ' + str(len(score_map)))

works = list(db.execute('SELECT title_id FROM works').fetchall())
updates, updated = [], 0

for (tid,) in works:
    aw    = awards_fk.get(tid, [])
    score = score_map.get(tid)

    wins  = [a for a in aw if a['lvl'] == 1]
    noms  = [a for a in aw if 2 <= a['lvl'] <= 8]
    polls = [a for a in aw if 10 <= a['lvl'] <= 71]

    parts = []
    for a in wins:
        parts.append('🏆 ' + a['award_type_name'] + ' – ' + a['award_cat_name'])
    for a in noms:
        parts.append('🏅 ' + a['award_type_name'] + ' – ' + a['award_cat_name'])
    for a in polls:
        parts.append('📊 ' + a['award_type_name'] + ' #' + str(a['lvl']) + ' – ' + a['award_cat_name'])

    # award_count = victoires + nominations (pas les sondages)
    count = len(wins) + len(noms)
    if count == 0 and score:
        count = 1  # présent dans award_titles_report = cité quelque part

    updates.append({
        'title_id':    tid,
        'awards':      ' | '.join(parts) if parts else None,
        'award_count': count,
        'award_score': score,
    })
    if count > 0: updated += 1

print('Ecriture...')
db['works'].upsert_all(updates, pk='title_id')
print('OK ' + str(updated) + ' oeuvres avec awards')

print('DP sans VF primees/nominées: ' + str(db.execute(
    'SELECT COUNT(*) FROM works WHERE (dp_eu=1 OR dp_us=1) AND has_french_vf=0 AND award_count>0'
).fetchone()[0]))

print('=== Top 20 romans DP sans VF par nb victoires+noms ===')
for r in db.execute("""
    SELECT title, author, year, award_count, award_score, awards
    FROM works WHERE type='novel' AND (dp_eu=1 OR dp_us=1)
      AND has_french_vf=0 AND award_count>0
    ORDER BY award_count DESC, award_score DESC LIMIT 20
""").fetchall():
    print(r)

cn.close()
