"""
21b_translators_noosfere.py
Complète les traducteurs non trouvés sur Wikidata via noosfere (Crawl4AI).
"""
import fcntl, sys
_lf = open("/app/data/21b.lock", "w")
try:
    fcntl.flock(_lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
except IOError:
    print("Instance deja en cours. Abandon."); sys.exit(0)

import sqlite3, logging, time, re, asyncio
from datetime import datetime
from crawl4ai import AsyncWebCrawler

DB       = '/app/data/sf_dp.sqlite'
LOG_FILE = '/app/data/21b_noosfere.log'

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-7s %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()])
log = logging.getLogger()
log.info('=== 21b_translators_noosfere.py ===')

conn = sqlite3.connect(DB, timeout=60)
conn.row_factory = sqlite3.Row
sc = conn.cursor()

# Extraire traducteurs non trouvés
sc.execute("""
    SELECT name FROM translators 
    WHERE death_year IS NULL 
    AND searched=1
    ORDER BY name
""")
not_found = [r['name'] for r in sc.fetchall()]
log.info(f'{len(not_found)} traducteurs non trouvés sur Wikidata')

async def scrape_noosfere(name):
    """Scrape noosfere avec Crawl4AI."""
    try:
        search_url = f"https://www.noosfere.org/livres/niourf.asp?Mots={name}"
        
        async with AsyncWebCrawler(verbose=False) as crawler:
            result = await crawler.arun(
                url=search_url,
                word_count_threshold=10,
                delay_before_return_html=2.0
            )
            
            if not result.success or not result.html:
                return None
            
            # Extraire lien auteur
            match = re.search(r'auteur\.asp\?numauteur=(\d+)', result.html)
            if not match:
                return None
            
            num_auteur = match.group(1)
            author_url = f"https://www.noosfere.org/livres/auteur.asp?numauteur={num_auteur}"
            
            # Fetch page auteur
            author_result = await crawler.arun(
                url=author_url,
                word_count_threshold=50,
                delay_before_return_html=2.0
            )
            
            if not author_result.success:
                return None
            
            text = author_result.markdown or ''
            
            # Extraire dates
            birth = re.search(r'Naissance.*?(\d{4})', text)
            death = re.search(r'Décès.*?(\d{4})', text)
            
            if death:
                return {
                    'birth_year': int(birth.group(1)) if birth else None,
                    'death_year': int(death.group(1)),
                    'noosfere_id': num_auteur,
                    'source': 'noosfere'
                }
    
    except Exception as e:
        log.warning(f'Noosfere error {name}: {e}')
    
    return None

n_found = n_notfound = 0

async def main():
    global n_found, n_notfound
    
    for i, name in enumerate(not_found):
        data = await scrape_noosfere(name)
        
        if data:
            dp_year = data['death_year'] + 71
            sc.execute("""
                UPDATE translators 
                SET birth_year=?, death_year=?, noosfere_id=?, dp_year=?, source=?
                WHERE name=?
            """, (data['birth_year'], data['death_year'], 
                  data['noosfere_id'], dp_year, data['source'], name))
            
            n_found += 1
            dp_status = '✅ DP' if dp_year <= 2026 else f'🔒 {dp_year}'
            log.info(f'[{i+1:3d}/{len(not_found)}] ✓ {name:30s} †{data["death_year"]} {dp_status}')
        else:
            n_notfound += 1
        
        if (i+1) % 50 == 0:
            conn.commit()
            log.info(f'CHECKPOINT {i+1}/{len(not_found)} — trouvés:{n_found} non trouvés:{n_notfound}')
        
        await asyncio.sleep(1.5)  # Rate limiting

asyncio.run(main())
conn.commit()

log.info(f'\n✅ Noosfere: {n_found} trouvés / {n_notfound} non trouvés')
log.info(f'Terminé {datetime.now().strftime("%H:%M:%S")}')
conn.close()
_lf.close()
