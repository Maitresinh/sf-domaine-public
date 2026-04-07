"""22d_magazines_dp.py - Nouvelles DP dans magazines (15381 cibles)"""
import fcntl, sys
_lf = open("/app/data/22d.lock", "w")
try:
    fcntl.flock(_lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
except IOError:
    print("Instance en cours."); sys.exit(0)

import sqlite3, logging, asyncio, re
from datetime import datetime
from crawl4ai import AsyncWebCrawler

DB = '/app/data/sf_dp.sqlite'
LOG_FILE = '/app/data/22d_magazines.log'

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()])
log = logging.getLogger()

conn = sqlite3.connect(DB, timeout=60)
conn.row_factory = sqlite3.Row
sc = conn.cursor()

log.info('=== 22d_magazines_dp.py ===')
sc.execute("""
    SELECT title_id, title, author, year
    FROM works
    WHERE (dp_eu=1 OR dp_us=1) AND goodreads_id IS NULL
      AND mag_title IS NOT NULL
      AND "type" IN ('short story','shortfiction','novelette','novella')
    ORDER BY year DESC, annualviews DESC NULLS LAST
""")
targets = list(sc.fetchall())
log.info(f'{len(targets)} nouvelles magazines sans GR (estimé 21h)')

async def search(title, author):
    async with AsyncWebCrawler(verbose=False) as crawler:
        result = await crawler.arun(
            url=f"https://www.goodreads.com/search?q={title} {author}",
            word_count_threshold=10, bypass_cache=True)
        if result.success:
            m = re.search(r'book/show/(\d+)', result.markdown or "")
            return m.group(1) if m else None
    return None

async def main():
    n_ok = n_skip = 0
    for i, r in enumerate(targets, 1):
        gr_id = await search(r['title'], r['author'])
        if gr_id:
            sc.execute("UPDATE works SET goodreads_id=? WHERE title_id=?", (gr_id, r['title_id']))
            n_ok += 1
            log.info(f'[{i}/{len(targets)}] ✓ {r["author"][:20]} — {r["title"][:40]} → {gr_id}')
        else:
            n_skip += 1
        if i % 50 == 0:
            conn.commit()
            log.info(f'CHECKPOINT {i}/{len(targets)} — OK:{n_ok} SKIP:{n_skip}')
        await asyncio.sleep(2)
    conn.commit()
    log.info(f'\n✅ {n_ok}/{len(targets)} trouvés ({100*n_ok/len(targets):.1f}%)')

asyncio.run(main())
conn.close()
_lf.close()
