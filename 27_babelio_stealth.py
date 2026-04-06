"""
27_babelio_stealth.py
Version anti-détection avec session persistante + headers rotatifs.
"""
import fcntl, sys
_lf = open("/app/data/27s.lock", "w")
try:
    fcntl.flock(_lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
except IOError:
    print("Instance deja en cours. Abandon."); sys.exit(0)

import sqlite3, logging, time, re, asyncio, random
from datetime import datetime
from crawl4ai import AsyncWebCrawler

DB       = '/app/data/sf_dp.sqlite'
LOG_FILE = '/app/data/27_stealth.log'
BATCH    = 20

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()])
log = logging.getLogger()
log.info('=== 27_babelio_stealth.py ===')

conn = sqlite3.connect(DB, timeout=60)
conn.row_factory = sqlite3.Row
sc = conn.cursor()

# Cibles VF
sc.execute("""
    SELECT title_id, title, author, year, last_vf_title, death_year
    FROM works
    WHERE has_french_vf=1 AND babelio_url IS NULL
    ORDER BY 
        CASE WHEN last_vf_year <= 1995 THEN 1 
             WHEN death_year BETWEEN 1956 AND 1971 THEN 2 
             ELSE 3 END,
        award_count DESC, annualviews DESC NULLS LAST
    LIMIT 500
""")
targets = list(sc.fetchall())
log.info(f'{len(targets)} cibles prioritaires (VF ≤1995 + Anticipation)')

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]

async def search_babelio(title_vf, author):
    """Recherche sur Babelio avec headers rotatifs."""
    query = f"{title_vf} {author}".strip()
    url = f"https://www.babelio.com/resrecherche.php?Recherche={query}"
    
    try:
        # Headers aléatoires
        headers = {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://www.google.com/'
        }
        
        result = await crawler.arun(
            url=url,
            word_count_threshold=10,
            bypass_cache=True,
            headers=headers,
            viewport_width=random.randint(1366, 1920),
            viewport_height=random.randint(768, 1080)
        )
        
        if not result.success:
            return None, None, None
        
        text = result.markdown or ""
        
        # Extraction rating
        rating_match = re.search(r'Note moyenne\s*:\s*([\d.]+)', text)
        rating = float(rating_match.group(1)) if rating_match else None
        
        # URL livre
        url_match = re.search(r'https://www\.babelio\.com/livres/[^/]+/[\w-]+/\d+', text)
        book_url = url_match.group(0) if url_match else None
        
        return rating, None, book_url
        
    except Exception as e:
        log.warning(f'  Erreur {title_vf}: {str(e)[:100]}')
        return None, None, None

async def main():
    global crawler
    n_found = n_skip = 0
    
    # Session persistante
    async with AsyncWebCrawler(verbose=False) as crawler:
        for i, r in enumerate(targets, 1):
            title_vf = r['last_vf_title'] or r['title']
            
            rating, reviews, url = await search_babelio(title_vf, r['author'])
            
            if url:
                sc.execute("""
                    UPDATE works 
                    SET babelio_rating=?, babelio_url=?
                    WHERE title_id=?
                """, (rating, url, r['title_id']))
                n_found += 1
                log.info(f'  [{i}/{len(targets)}] ✓ {r["author"][:20]} — {title_vf[:30]} → {rating or "?"} {url}')
            else:
                n_skip += 1
            
            # Commit régulier
            if i % BATCH == 0:
                conn.commit()
                log.info(f'CHECKPOINT {i}/{len(targets)} — trouvé:{n_found} échec:{n_skip}')
            
            # Rate limiting aléatoire 10-15s
            await asyncio.sleep(random.uniform(10, 15))
    
    conn.commit()
    log.info(f'✅ TERMINÉ — {n_found} trouvés, {n_skip} échecs')

asyncio.run(main())
conn.close()
_lf.close()
