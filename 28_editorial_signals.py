"""
28_editorial_signals.py
Identifie nouvelles prioritaires via signaux éditoriaux forts.

Signaux qualité :
- Awards (Hugo, Nebula, etc.)
- Traductions multiples (validation internationale)
- Goodreads rating élevé + votes
- annualviews élevé (popularité durable)
- Auteur prolifique traduit
"""
import sqlite3, json, logging
from datetime import datetime

DB = '/app/data/sf_dp.sqlite'
LOG_FILE = '/app/data/28_editorial_signals.log'

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()])
log = logging.getLogger()
log.info('=== 28_editorial_signals.py ===')

conn = sqlite3.connect(DB, timeout=60)
conn.row_factory = sqlite3.Row
sc = conn.cursor()

# Toutes les nouvelles DP (EU ou US)
log.info('Extraction nouvelles DP...')
sc.execute("""
    SELECT title_id, title, author, year, dp_eu, dp_us, has_french_vf,
           goodreads_id, gr_rating, gr_votes, award_count, awards,
           annualviews, nb_langues_vf, nb_editions, last_vf_year
    FROM works
    WHERE (dp_eu=1 OR dp_us=1)
    AND "type" IN ('short story', 'shortfiction', 'novelette', 'novella')
""")

stories = list(sc.fetchall())
log.info(f'{len(stories)} nouvelles DP trouvées')

# Calcul auteur stats (nb œuvres traduites)
log.info('Calcul stats auteurs...')
author_stats = {}
sc.execute("""
    SELECT author, COUNT(*) as nb_works, SUM(has_french_vf) as nb_translated
    FROM works
    WHERE author IS NOT NULL
    GROUP BY author
""")
for r in sc.fetchall():
    author_stats[r['author']] = {
        'nb_works': r['nb_works'],
        'nb_translated': r['nb_translated'] or 0
    }

# Scoring
log.info('Calcul scores éditoriaux...')
priorities = []

for r in stories:
    score = 0
    signals = []
    
    # 1. Awards (signal très fort)
    if r['award_count'] and r['award_count'] > 0:
        score += r['award_count'] * 20
        signals.append(f"{r['award_count']}🏆")
    
    # 2. Traductions multiples (validation internationale)
    if r['nb_langues_vf'] and r['nb_langues_vf'] >= 3:
        score += r['nb_langues_vf'] * 5
        signals.append(f"{r['nb_langues_vf']}lang")
    
    # 3. Goodreads rating élevé + votes
    if r['gr_rating'] and r['gr_rating'] >= 4.0:
        score += (r['gr_rating'] - 3.0) * 10
        signals.append(f"GR{r['gr_rating']:.1f}")
    
    if r['gr_votes'] and r['gr_votes'] >= 1000:
        score += min(r['gr_votes'] / 200, 20)
        signals.append(f"{r['gr_votes']}votes")
    
    # 4. annualviews élevé (popularité durable)
    if r['annualviews'] and r['annualviews'] >= 500:
        score += r['annualviews'] / 100
        signals.append(f"{r['annualviews']}views")
    
    # 5. Auteur reconnu (beaucoup d'œuvres traduites)
    author = r['author']
    if author in author_stats:
        nb_trans = author_stats[author]['nb_translated']
        if nb_trans >= 10:
            score += min(nb_trans / 2, 20)
            signals.append(f"auteur:{nb_trans}VF")
    
    # 6. Bonus si manques à combler
    if not r['goodreads_id']:
        score += 15
        signals.append('NO_GR')
    
    if not r['has_french_vf']:
        score += 10
        signals.append('NO_VF')
    
    # 7. Bonus DP US (moins de risque juridique)
    if r['dp_us'] == 1:
        score += 5
    
    # 8. Pénalité si traduit récemment (moins intéressant)
    if r['last_vf_year'] and r['last_vf_year'] >= 2000:
        score -= 10
    
    priorities.append({
        'title_id': r['title_id'],
        'title': r['title'],
        'author': r['author'],
        'year': r['year'],
        'dp_us': r['dp_us'],
        'dp_eu': r['dp_eu'],
        'has_vf': r['has_french_vf'],
        'gr_id': r['goodreads_id'],
        'gr_rating': r['gr_rating'],
        'awards': r['award_count'],
        'nb_langues': r['nb_langues_vf'],
        'annualviews': r['annualviews'],
        'score': score,
        'signals': signals
    })

priorities.sort(key=lambda x: x['score'], reverse=True)

# Stats
log.info(f'\n=== STATS GLOBALES ===')
log.info(f'Total nouvelles DP: {len(priorities)}')

nb_dp_us = sum(1 for p in priorities if p['dp_us'])
nb_no_vf = sum(1 for p in priorities if not p['has_vf'])
nb_no_gr = sum(1 for p in priorities if not p['gr_id'])
nb_awards = sum(1 for p in priorities if p['awards'] and p['awards'] > 0)

log.info(f'DP US: {nb_dp_us} ({100*nb_dp_us/len(priorities):.1f}%)')
log.info(f'Sans VF: {nb_no_vf} ({100*nb_no_vf/len(priorities):.1f}%)')
log.info(f'Sans GR: {nb_no_gr} ({100*nb_no_gr/len(priorities):.1f}%)')
log.info(f'Avec awards: {nb_awards} ({100*nb_awards/len(priorities):.1f}%)')

# Top 100
log.info('\n=== TOP 100 NOUVELLES PRIORITAIRES (signaux éditoriaux) ===')
for i, p in enumerate(priorities[:100], 1):
    dp = 'EU+US' if p['dp_eu'] and p['dp_us'] else 'US' if p['dp_us'] else 'EU'
    vf = '✅' if p['has_vf'] else '❌'
    gr = '✓' if p['gr_id'] else '✗'
    
    log.info(f'{i:3d}. [{p["score"]:5.0f}] {p["author"][:20]:20s} — {p["title"][:35]:35s} ({p["year"]}) | DP:{dp} VF:{vf} GR:{gr}')
    log.info(f'     Signaux: {", ".join(p["signals"][:5])}')

# Segments stratégiques
log.info('\n=== SEGMENTS STRATÉGIQUES ===')

# Segment 1 : Perles cachées (awards + pas de VF)
perles = [p for p in priorities if p['awards'] and p['awards'] > 0 and not p['has_vf']][:20]
log.info(f'\n1. PERLES CACHÉES ({len(perles)} primées sans VF):')
for i, p in enumerate(perles, 1):
    log.info(f'{i:2d}. {p["author"][:20]:20s} — {p["title"][:40]:40s} ({p["year"]}) | {p["awards"]}🏆')

# Segment 2 : Validation internationale (3+ langues, pas VF)
intl = [p for p in priorities if p['nb_langues'] and p['nb_langues'] >= 3 and not p['has_vf']][:20]
log.info(f'\n2. VALIDATION INTERNATIONALE ({len(intl)} traduites 3+ langues sans VF):')
for i, p in enumerate(intl, 1):
    log.info(f'{i:2d}. {p["author"][:20]:20s} — {p["title"][:40]:40s} ({p["year"]}) | {p["nb_langues"]}lang')

# Segment 3 : Popularité durable (annualviews élevé)
populaires = [p for p in priorities if p['annualviews'] and p['annualviews'] >= 1000][:20]
log.info(f'\n3. POPULARITÉ DURABLE ({len(populaires)} >1000 views/an):')
for i, p in enumerate(populaires, 1):
    log.info(f'{i:2d}. {p["author"][:20]:20s} — {p["title"][:40]:40s} ({p["year"]}) | {p["annualviews"]}views')

log.info(f'\n✅ TERMINE {datetime.now().strftime("%H:%M:%S")}')
conn.close()
