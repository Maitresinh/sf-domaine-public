"""
22b_novels_dp.py
Recherche goodreads_id pour TOUS les romans/collections DP (pas les nouvelles).
Meilleur taux de succès que les short stories.

Cibles : 9669 romans DP sans goodreads_id
Durée : ~13h25
"""
import fcntl, sys
_lf = open("/app/data/22b.lock", "w")
try:
    fcntl.flock(_lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
except IOError:
    print("Instance deja en cours. Abandon."); sys.exit(0)

import sqlite3, logging, time, re, asyncio
from datetime import datetime
from crawl4ai import AsyncWebCrawler

DB       = '/app/data/sf_dp.sqlite'
LOG_FILE = '/app/data/22b_novels.log'
BATCH    = 50

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-7s %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()])
log = logging.getLogger()
log.info('=== 22b_novels_dp.py ===')

conn = sqlite3.connect(DB, timeout=60)
conn.row_factory = sqlite3.Row
sc = conn.cursor()

# Romans/collections DP sans goodreads_id (ordre année DESC = plus récent d'abord)
log.info('Extraction romans DP...')
sc.execute("""
    SELECT title_id, title, author, year
    FROM works
    WHERE (dp_eu=1 OR dp_us=1)
      AND goodreads_id IS NULL
      AND "type" NOT IN ('short story','shortfiction','novelette','novella')
    ORDER BY year DESC, annualviews DESC NULLS LAST
""")
targets = list(sc.fetchall())
log.info(f'{len(targets)} romans DP sans goodreads_id (1963→1920)')

async def search_goodreads(title, author):
    """Recherche goodreads_id via search."""
    query = f"{title} {author}".strip()
    url = f"https://www.goodreads.com/search?q={query}&search_type=books"
    
    try:
        async with AsyncWebCrawler(verbose=False) as crawler:
            result = await crawler.arun(
                url=url,
                word_count_threshold=10,
                wait_for="css:.leftContainer",
                delay_before_return_html=2.0
            )
            
            if result.success and result.html:
                match = re.search(r'/book/show/(\d+)', result.html)
                if match:
                    return match.group(1)
    except Exception as e:
        log.warning(f'Search error {title[:30]}: {e}')
    
    return None

async def process_batch(batch):
    """Traite un batch de recherches."""
    results = []
    for row in batch:
        gid = await search_goodreads(row['title'], row['author'])
        results.append((row['title_id'], gid))
        await asyncio.sleep(0.5)
    return results

n_done = n_found = n_notfound = 0

async def main():
    global n_done, n_found, n_notfound
    
    for i in range(0, len(targets), BATCH):
        batch = targets[i:i+BATCH]
        
        results = await process_batch(batch)
        
        for tid, gid in results:
            if gid:
                sc.execute("UPDATE works SET goodreads_id=? WHERE title_id=?", (gid, tid))
                n_found += 1
                if n_found <= 20 or n_found % 100 == 0:
                    row = next(r for r in batch if r['title_id'] == tid)
                    log.info(f'[{n_done+1}/{len(targets)}] ✓ {row["author"][:20]} — {row["title"][:40]} ({row["year"]}) → {gid}')
            else:
                n_notfound += 1
            
            n_done += 1
        
        conn.commit()
        if (i + BATCH) % 200 == 0:
            log.info(f'CHECKPOINT {n_done}/{len(targets)} — trouvés:{n_found} non trouvés:{n_notfound}')

asyncio.run(main())

log.info('\n=== RESULTATS ===')
log.info(f'  Total traité       : {n_done:5d}')
log.info(f'  Goodreads_id trouvé: {n_found:5d} ({n_found/n_done*100:.1f}%)')
log.info(f'  Non trouvé         : {n_notfound:5d}')

log.info(f'\n✅ TERMINE {datetime.now().strftime("%H:%M:%S")}')
conn.close()
_lf.close()
