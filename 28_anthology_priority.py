"""28_anthology_priority.py - Score nouvelles DP"""
import sqlite3, logging
from datetime import datetime

DB = '/app/data/sf_dp.sqlite'
LOG_FILE = '/app/data/28_priority.log'

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()])
log = logging.getLogger()

conn = sqlite3.connect(DB, timeout=60)
conn.row_factory = sqlite3.Row
sc = conn.cursor()

log.info('=== 28_anthology_priority.py ===')

sc.execute("""
    SELECT title, author, year, has_french_vf, goodreads_id, 
           gr_rating, award_count, nb_langues_vf, annualviews
    FROM works
    WHERE (dp_eu=1 OR dp_us=1)
    AND "type" IN ('short story', 'shortfiction', 'novelette', 'novella')
    AND (award_count > 0 OR nb_langues_vf >= 3 OR gr_rating >= 4.0)
""")

stories = list(sc.fetchall())
log.info(f'{len(stories)} nouvelles DP avec signaux forts')

priorities = []
for r in stories:
    score = 0
    if r['award_count']: score += int(r['award_count']) * 20
    if r['nb_langues_vf'] and r['nb_langues_vf'] >= 3: score += r['nb_langues_vf'] * 5
    if r['gr_rating']: score += (float(r['gr_rating']) - 3.0) * 10
    if r['annualviews']: score += int(r['annualviews']) / 100
    if not r['goodreads_id']: score += 15
    if not r['has_french_vf']: score += 10
    
    priorities.append({'title': r['title'], 'author': r['author'], 'year': r['year'],
                      'score': score, 'has_vf': r['has_french_vf']})

priorities.sort(key=lambda x: x['score'], reverse=True)

log.info('\n=== TOP 50 NOUVELLES PRIORITAIRES ===')
for i, p in enumerate(priorities[:50], 1):
    vf = '✅' if p['has_vf'] else '❌'
    log.info(f'{i:2d}. [{p["score"]:5.0f}] {p["author"][:20]:20s} — {p["title"][:40]:40s} ({p["year"]}) VF:{vf}')

log.info(f'\n✅ TERMINÉ')
conn.close()
