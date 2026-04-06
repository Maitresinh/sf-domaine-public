"""
28_anthology_priority.py
Identifie nouvelles prioritaires via présence dans anthologies "Best of".

Logique :
1. Extraire nouvelles des anthologies de référence (contents_json)
2. Scorer par : nb_anthologies + awards + annualviews
3. Prioriser : DP US + pas de GR + pas de VF
"""
import sqlite3, json, logging
from datetime import datetime

DB = '/app/data/sf_dp.sqlite'
LOG_FILE = '/app/data/28_anthology_priority.log'

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()])
log = logging.getLogger()
log.info('=== 28_anthology_priority.py ===')

conn = sqlite3.connect(DB, timeout=60)
conn.row_factory = sqlite3.Row
sc = conn.cursor()

# Anthologies de référence (liste exhaustive)
REFERENCE_ANTHOLOGIES = [
    # Hall of Fame
    'Science Fiction Hall of Fame',
    'The Science Fiction Hall of Fame',
    
    # Best of year
    'The Best Science Fiction of the Year',
    'The Year\'s Best Science Fiction',
    'Best SF',
    'World\'s Best Science Fiction',
    
    # Nebula/Hugo compilations
    'Nebula Award Stories',
    'Nebula Awards Showcase',
    'The Hugo Winners',
    'Hugo and Nebula Award Winners',
    
    # Éditeurs historiques
    'Adventures in Time and Space',  # Healy & McComas 1946
    'The Astounding Science Fiction Anthology',
    'A Treasury of Great Science Fiction',
    'The Magazine of Fantasy & Science Fiction',
    
    # Thématiques classiques
    'The Golden Age of Science Fiction',
    'Modern Masterpieces of Science Fiction',
    'Great Science Fiction Stories',
    'Classic Science Fiction',
    'Science Fiction: The Great Years',
    
    # Éditeurs célèbres
    'The Road to Science Fiction',  # James Gunn
    'Dangerous Visions',  # Harlan Ellison
    'Again, Dangerous Visions',
    'The Mirror of Infinity',  # Robert Silverberg
    
    # Collections "Best"
    'Best of the Best',
    'The Greatest Science Fiction Stories',
    'Science Fiction Masterpieces',
    'The Oxford Book of Science Fiction',
    'The Wesleyan Anthology of Science Fiction',
]

# Extraire anthologies correspondantes
log.info('Recherche anthologies de référence...')
placeholders = ','.join(['?' for _ in REFERENCE_ANTHOLOGIES])

# Recherche exacte + LIKE
found_anthologies = []
for ref in REFERENCE_ANTHOLOGIES:
    sc.execute("""
        SELECT title_id, title, year, contents_json
        FROM works
        WHERE (title LIKE ? OR title = ?)
        AND contents_json IS NOT NULL
        AND "type" IN ('anthology', 'collection')
    """, (f'%{ref}%', ref))
    
    for r in sc.fetchall():
        found_anthologies.append(r)

log.info(f'{len(found_anthologies)} anthologies de référence trouvées')

# Afficher les anthologies trouvées
log.info('\n=== ANTHOLOGIES TROUVÉES ===')
for a in found_anthologies[:20]:  # Top 20
    log.info(f'  [{a["year"] or "?"}] {a["title"][:60]}')
if len(found_anthologies) > 20:
    log.info(f'  ... et {len(found_anthologies)-20} autres')

# Extraire toutes les nouvelles mentionnées
log.info('\nExtraction nouvelles...')
story_counts = {}  # title_id -> nb_anthologies
story_anthologies = {}  # title_id -> [anthology names]

for antho in found_anthologies:
    try:
        contents = json.loads(antho['contents_json'])
        for story in contents:
            tid = story.get('title_id')
            if tid:
                story_counts[tid] = story_counts.get(tid, 0) + 1
                if tid not in story_anthologies:
                    story_anthologies[tid] = []
                story_anthologies[tid].append(antho['title'][:50])
    except:
        pass

log.info(f'{len(story_counts)} nouvelles uniques dans anthologies')

# Scorer et trier
log.info('Calcul scores priorité...')
priorities = []
for tid, nb_antho in story_counts.items():
    r = sc.execute("""
        SELECT title, author, year, dp_eu, dp_us, has_french_vf,
               goodreads_id, award_count, annualviews, gr_rating
        FROM works WHERE title_id=?
    """, (tid,)).fetchone()
    
    if not r:
        continue
    
    # Score priorité
    score = nb_antho * 10  # Nb anthologies (poids fort)
    score += (r['award_count'] or 0) * 5
    score += (r['annualviews'] or 0) / 1000
    score += (r['gr_rating'] or 0) * 2
    
    # Bonus si manques critiques
    if not r['goodreads_id']:
        score += 20
    if not r['has_french_vf']:
        score += 15
    if r['dp_us'] == 1:
        score += 10
    
    priorities.append({
        'title_id': tid,
        'title': r['title'],
        'author': r['author'],
        'year': r['year'],
        'nb_antho': nb_antho,
        'anthologies': story_anthologies[tid],
        'dp_us': r['dp_us'],
        'dp_eu': r['dp_eu'],
        'has_vf': r['has_french_vf'],
        'gr_id': r['goodreads_id'],
        'gr_rating': r['gr_rating'],
        'awards': r['award_count'],
        'score': score
    })

priorities.sort(key=lambda x: x['score'], reverse=True)

# Stats
nb_dp_us = sum(1 for p in priorities if p['dp_us'])
nb_no_vf = sum(1 for p in priorities if not p['has_vf'])
nb_no_gr = sum(1 for p in priorities if not p['gr_id'])

log.info(f'\n=== STATS GLOBALES ===')
log.info(f'Total nouvelles: {len(priorities)}')
log.info(f'DP US: {nb_dp_us} ({100*nb_dp_us/len(priorities):.1f}%)')
log.info(f'Sans VF: {nb_no_vf} ({100*nb_no_vf/len(priorities):.1f}%)')
log.info(f'Sans GR: {nb_no_gr} ({100*nb_no_gr/len(priorities):.1f}%)')

# Top 50
log.info('\n=== TOP 50 NOUVELLES PRIORITAIRES (via anthologies) ===')
for i, p in enumerate(priorities[:50], 1):
    dp = 'EU+US' if p['dp_eu'] and p['dp_us'] else 'US' if p['dp_us'] else 'EU' if p['dp_eu'] else '❌'
    vf = '✅' if p['has_vf'] else '❌'
    gr = '✓' if p['gr_id'] else '✗'
    rating = f'{p["gr_rating"]:.1f}' if p['gr_rating'] else '?'
    awards = f'{p["awards"]}🏆' if p['awards'] else ''
    
    log.info(f'{i:2d}. [{p["score"]:5.0f}] {p["author"][:20]:20s} — {p["title"][:35]:35s} ({p["year"]}) | {p["nb_antho"]}x | DP:{dp:5s} VF:{vf} GR:{gr} {rating} {awards}')
    
    # Afficher 1-2 anthologies sources
    if i <= 20:
        log.info(f'    ↳ dans: {", ".join(p["anthologies"][:2])}{"..." if len(p["anthologies"]) > 2 else ""}')

# Cibles prioritaires pour enrichissement
log.info('\n=== CIBLES ENRICHISSEMENT ===')
log.info('Nouvelles DP US sans GR (priorité recherche goodreads_id):')
targets_no_gr = [p for p in priorities if p['dp_us'] and not p['gr_id']][:20]
for i, p in enumerate(targets_no_gr, 1):
    log.info(f'{i:2d}. {p["author"][:20]:20s} — {p["title"][:40]:40s} ({p["year"]}) | {p["nb_antho"]}antho')

log.info(f'\n✅ TERMINE {datetime.now().strftime("%H:%M:%S")}')
conn.close()
