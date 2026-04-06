"""
21c_translator_death_estimate.py
Estime si traducteur probablement décédé (pragmatisme éditorial).
NE calcule PAS le DP de la traduction, juste mort présumée.
"""
import sqlite3, logging
from datetime import datetime

DB = '/app/data/sf_dp.sqlite'
LOG_FILE = '/app/data/21c_death_estimate.log'

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()])
log = logging.getLogger()

conn = sqlite3.connect(DB, timeout=60)
conn.row_factory = sqlite3.Row
sc = conn.cursor()

log.info('=== 21c_translator_death_estimate.py ===')

# Traducteurs sans death_year
sc.execute("""
    SELECT name, birth_year
    FROM translators
    WHERE death_year IS NULL
""")

translators = list(sc.fetchall())
log.info(f'{len(translators)} traducteurs sans death_year')

# Pour chaque traducteur, chercher première/dernière traduction
estimated = 0

for trans in translators:
    name = trans['name']
    
    # Première et dernière traduction
    sc.execute("""
        SELECT MIN(first_vf_year) as first_trans,
               MAX(last_vf_year) as last_trans
        FROM works
        WHERE last_vf_translator = ?
        AND first_vf_year IS NOT NULL
    """, (name,))
    
    r = sc.fetchone()
    if not r or not r['first_trans']:
        continue
    
    first_trans = r['first_trans']
    last_trans = r['last_trans'] or first_trans
    
    # Heuristique : présumé mort si inactif ≥40 ans
    years_inactive = 2026 - int(last_trans)
    
    if years_inactive >= 40:
        # Estimation mort : dernière activité + 10 ans
        death_estimate = last_trans + 10
        
        sc.execute("""
            UPDATE translators
            SET death_year = ?,
                death_year_source = 'heuristique_inactivite'
            WHERE name = ?
        """, (death_estimate, name))
        
        estimated += 1
        log.info(f'  {name:30s} | 1ère:{first_trans} dernière:{last_trans} → †{death_estimate}? (inactif {years_inactive}ans)')

conn.commit()
conn.close()

log.info(f'\n✅ {estimated} morts estimées par inactivité')
log.info(f'TERMINÉ {datetime.now().strftime("%H:%M:%S")}')
