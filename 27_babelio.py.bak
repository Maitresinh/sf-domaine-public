"""
27_babelio.py
Enrichissement critiques françaises via Babelio pour œuvres avec VF.

Cibles (4498 œuvres) :
  P1 - VF anciennes ≤1995 (DP traduction potentielle)
  P2 - Anticipation 1956-1971 avec VF
  P3 - Tout DP avec VF

Extraction :
  - babelio_rating (note moyenne)
  - babelio_votes (nombre de votants)
  - babelio_reviews_text (JSON: 3-5 extraits critiques FR)
  - babelio_url
"""
import fcntl, sys
_lf = open("/app/data/27.lock", "w")
try:
    fcntl.flock(_lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
except IOError:
    print("Instance deja en cours. Abandon."); sys.exit(0)

import sqlite3, logging, time, re, asyncio, json, random
from datetime import datetime
from crawl4ai import AsyncWebCrawler

DB       = '/app/data/sf_dp.sqlite'
LOG_FILE = '/app/data/27_babelio.log'
BATCH    = 20

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-7s %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()])
log = logging.getLogger()
log.info('=== 27_babelio.py ===')

conn = sqlite3.connect(DB, timeout=60)
conn.row_factory = sqlite3.Row
sc = conn.cursor()

# Colonnes Babelio
for col in ['babelio_rating', 'babelio_votes', 'babelio_reviews_text', 'babelio_url']:
    try:
        sc.execute(f'ALTER TABLE works ADD COLUMN {col} TEXT')
    except:
        pass
conn.commit()

# Extraction cibles (ordre priorité)
log.info('Extraction cibles avec VF...')
sc.execute("""
    SELECT title_id, title, author, year, last_vf_title, last_vf_year,
           dp_eu, dp_us, death_year, award_count, annualviews, nb_langues_vf
    FROM works
    WHERE has_french_vf=1
      AND (babelio_rating IS NULL OR babelio_rating = '')
      AND (
          -- P1: VF anciennes
          (dp_eu=1 AND dp_us=1 
           AND last_vf_year IS NOT NULL 
           AND CAST(last_vf_year AS INTEGER) <= 1995)
          OR
          -- P2: Anticipation avec VF
          (death_year BETWEEN 1956 AND 1971
           AND (CAST(annualviews AS INTEGER)/1000 
                + COALESCE(nb_langues_vf,0)*5 
                + COALESCE(award_score,0)) >= 5)
          OR
          -- P3: Tout DP avec VF
          (dp_eu=1 OR dp_us=1)
      )
    ORDER BY
        CASE 
            WHEN dp_eu=1 AND dp_us=1 AND CAST(last_vf_year AS INTEGER)<=1995 THEN 1
            WHEN death_year BETWEEN 1956 AND 1971 THEN 2
            ELSE 3
        END,
        award_count DESC NULLS LAST,
        annualviews DESC NULLS LAST
""")
targets = list(sc.fetchall())
log.info(f'{len(targets)} cibles avec VF française')

p1 = sum(1 for r in targets if r['dp_eu']==1 and r['dp_us']==1 and r['last_vf_year'] and int(r['last_vf_year'])<=1995)
p2 = sum(1 for r in targets if r['death_year'] and 1956<=r['death_year']<=1971)
p3 = len(targets) - p1 - p2
log.info(f'  P1 (VF ≤1995)    : {p1}')
log.info(f'  P2 (Anticip VF)  : {p2}')
log.info(f'  P3 (Autre DP VF) : {p3}')

async def scrape_babelio(title_fr, author, title_en):
    """Scrape Babelio pour rating + critiques."""
    # Recherche par titre français d'abord
    queries = [
        f"{title_fr} {author}".strip() if title_fr else None,
        f"{title_en} {author}".strip()
    ]
    queries = [q for q in queries if q]
    
    for query in queries:
        try:
            search_url = f"https://www.babelio.com/resrecherche.php?Recherche={query}"
            
            async with AsyncWebCrawler(verbose=False) as crawler:
                result = await crawler.arun(
                    url=search_url,
                    word_count_threshold=10,
                    wait_for="css:.livre_header",
                    delay_before_return_html=2.5
                )
                
                if not result.success or not result.html:
                    continue
                
                # Extraire URL livre (premier résultat)
                match = re.search(r'href="(/livres/[^"]+)"', result.html)
                if not match:
                    continue
                
                book_url = "https://www.babelio.com" + match.group(1)
                
                # Fetch page livre
                book_result = await crawler.arun(
                    url=book_url,
                    word_count_threshold=50,
                    wait_for="css:.livre_header",
                    delay_before_return_html=2.5
                )
                
                if not book_result.success:
                    continue
                
                html = book_result.html
                text = book_result.markdown or ''
                
                # Extraire rating
                rating_match = re.search(r'(\d+[.,]\d+)/5', html)
                rating = rating_match.group(1).replace(',', '.') if rating_match else None
                
                # Extraire votes
                votes_match = re.search(r'(\d+)\s*(?:notes?|avis)', html, re.I)
                votes = votes_match.group(1) if votes_match else None
                
                # Extraire critiques (chercher blocs avec "Critique de")
                reviews = []
                for block in re.finditer(r'Critique de.{0,500}', text, re.DOTALL):
                    review = block.group(0)
                    # Nettoyer
                    review = re.sub(r'\s+', ' ', review).strip()
                    if len(review) > 50 and len(review) < 500:
                        reviews.append(review)
                    if len(reviews) >= 5:
                        break
                
                if rating or reviews:
                    return {
                        'rating': rating,
                        'votes': votes,
                        'reviews': reviews[:5],
                        'url': book_url
                    }
        
        except Exception as e:
            log.warning(f'Babelio error {query[:40]}: {e}')
            continue
    
    return None

n_done = n_found = n_notfound = 0

async def process_batch(batch):
    """Traite un batch."""
    results = []
    for row in batch:
        data = await scrape_babelio(
            row['last_vf_title'],
            row['author'],
            row['title']
        )
        results.append((row['title_id'], data))
        
        # Rate limiting variable
        await asyncio.sleep(random.uniform(8, 15))
    
    return results

async def main():
    global n_done, n_found, n_notfound
    
    for i in range(0, len(targets), BATCH):
        batch = targets[i:i+BATCH]
        
        results = await process_batch(batch)
        
        for tid, data in results:
            if data:
                reviews_json = json.dumps(data['reviews'], ensure_ascii=False)
                sc.execute("""
                    UPDATE works 
                    SET babelio_rating=?, babelio_votes=?, 
                        babelio_reviews_text=?, babelio_url=?
                    WHERE title_id=?
                """, (data['rating'], data['votes'], reviews_json, data['url'], tid))
                
                n_found += 1
                if n_found <= 20 or n_found % 50 == 0:
                    row = next(r for r in batch if r['title_id'] == tid)
                    vf = row['last_vf_title'][:30] if row['last_vf_title'] else '?'
                    log.info(f'[{n_done+1:4d}] ✓ {row["author"][:20]} — {vf} | {data["rating"] or "?"}/5 ({data["votes"] or "?"} avis) {len(data["reviews"])} critiques')
            else:
                n_notfound += 1
            
            n_done += 1
        
        conn.commit()
        if (i + BATCH) % 100 == 0:
            log.info(f'CHECKPOINT {n_done}/{len(targets)} — trouvés:{n_found} non trouvés:{n_notfound}')

asyncio.run(main())

log.info('\n=== RESULTATS ===')
log.info(f'  Total traité       : {n_done:5d}')
log.info(f'  Babelio trouvé     : {n_found:5d} ({n_found/n_done*100:.1f}%)')
log.info(f'  Non trouvé         : {n_notfound:5d}')

log.info(f'\n✅ TERMINE {datetime.now().strftime("%H:%M:%S")}')
conn.close()
_lf.close()
