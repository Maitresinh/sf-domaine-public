"""
23b_fix_first_vf.py
Remplit first_vf_year depuis editions_json pour corriger le problème.
CRITICAL pour identifier VF anciennes réutilisables.
"""
import sqlite3, json, logging
from datetime import datetime

DB = '/app/data/sf_dp.sqlite'
LOG_FILE = '/app/data/23b_fix_first_vf.log'

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()])
log = logging.getLogger()
log.info('=== 23b_fix_first_vf.py ===')

conn = sqlite3.connect(DB, timeout=60)
sc = conn.cursor()

# Extraire œuvres avec editions_json
sc.execute("SELECT title_id, editions_json FROM works WHERE editions_json IS NOT NULL")
rows = list(sc.fetchall())
log.info(f'{len(rows)} œuvres avec editions_json')

n_updated = 0

for tid, eds_json in rows:
    try:
        eds = json.loads(eds_json)
        
        # Chercher éditions françaises
        fr_years = []
        for e in eds:
            if e.get('lang_code') == 'fr':
                first = e.get('first_year')
                last = e.get('last_year')
                if first and str(first).isdigit():
                    fr_years.append(int(first))
                elif last and str(last).isdigit():
                    fr_years.append(int(last))
        
        if fr_years:
            first_vf = min(fr_years)
            last_vf = max(fr_years)
            
            sc.execute("""
                UPDATE works 
                SET first_vf_year=?, last_vf_year=?
                WHERE title_id=?
            """, (first_vf, last_vf, tid))
            
            n_updated += 1
            
            if n_updated <= 10 or n_updated % 1000 == 0:
                log.info(f'[{n_updated}] title_id={tid} → first={first_vf} last={last_vf}')
    
    except Exception as e:
        log.warning(f'Error title_id={tid}: {e}')
        continue
    
    if n_updated % 500 == 0:
        conn.commit()

conn.commit()
log.info(f'\n✅ {n_updated} œuvres mises à jour')
log.info(f'Terminé {datetime.now().strftime("%H:%M:%S")}')
conn.close()
