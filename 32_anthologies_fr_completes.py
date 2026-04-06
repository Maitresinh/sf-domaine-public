"""
32_anthologies_fr_completes.py
Extrait TOUTES les nouvelles des 2 collections majeures FR:
1. "Histoires de..." (Livre de Poche, 36 volumes)
2. "Les Meilleurs récits de..." (J'ai Lu, 14 volumes)

Puis matche avec DB et identifie DP sans VF.
"""
import fcntl, sys
_lf = open("/app/data/32.lock", "w")
try:
    fcntl.flock(_lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
except IOError:
    print("Instance deja en cours. Abandon."); sys.exit(0)

import sqlite3, logging, asyncio, re, random, requests
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler
from datetime import datetime

DB = '/app/data/sf_dp.sqlite'
LOG_FILE = '/app/data/32_anthologies_fr.log'

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()])
log = logging.getLogger()

COLLECTIONS = [
    {
        'name': 'Histoires de...',
        'serie_id': 2704,
        'publisher': 'Livre de Poche',
        'count': 36
    },
    {
        'name': 'Les Meilleurs récits de...',
        'serie_id': 410,
        'publisher': 'J\'ai Lu',
        'count': 14
    }
]

def get_book_ids_from_serie(serie_id):
    """Extrait IDs via requests + BeautifulSoup."""
    url = f'https://www.noosfere.org/livres/serie.asp?numserie={serie_id}'
    
    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        book_ids = []
        
        # Chercher tous les liens contenant numlivre
        for link in soup.find_all('a', href=True):
            if 'numlivre=' in link['href']:
                match = re.search(r'numlivre=(\d+)', link['href'])
                if match:
                    book_ids.append(match.group(1))
        
        # Aussi dans onclick
        for tag in soup.find_all(onclick=True):
            match = re.search(r'numlivre=(\d+)', tag['onclick'])
            if match:
                book_ids.append(match.group(1))
        
        return list(set(book_ids))
        
    except Exception as e:
        log.error(f'   Erreur série {serie_id}: {e}')
        return []

async def scrape_book_sommaire(numlivre):
    """Extrait sommaire avec Crawl4AI."""
    url = f'https://www.noosfere.org/livres/niourf.asp?numlivre={numlivre}'
    
    async with AsyncWebCrawler(verbose=False) as crawler:
        result = await crawler.arun(url=url, word_count_threshold=10)
        
        if not result.success:
            return None, []
        
        html = result.html or ""
        
        # Titre
        title_match = re.search(r'<title>([^<]+?)\s*[-–]\s*noosfere', html, re.IGNORECASE)
        book_title = title_match.group(1).strip() if title_match else f"#{numlivre}"
        
        stories = []
        
        # Pattern nouvelles: Auteur, «Titre»
        for match in re.finditer(r'([A-Z][\w\s\-\'\.]+?)\s*,\s*[«"]([^»"]{5,120})[»"]', html):
            author = match.group(1).strip()
            title = match.group(2).strip()
            
            # Nettoyer
            author = re.sub(r'\s*\([^\)]+\)', '', author)
            
            # Filtrer
            if len(title) >= 5 and len(author) >= 3:
                if not any(x in title.lower() for x in ['introduction', 'préface', 'postface', 'avant-propos']):
                    stories.append({
                        'author': author,
                        'title_vf': title,
                        'anthology': book_title
                    })
        
        return book_title, stories

async def main():
    log.info('='*70)
    log.info('32_anthologies_fr_completes.py')
    log.info('Extraction complète collections FR majeures')
    log.info('='*70)
    
    conn = sqlite3.connect(DB, timeout=60)
    sc = conn.cursor()
    
    all_stories = []
    
    for collection in COLLECTIONS:
        log.info(f"\n📚 {collection['name']}")
        log.info(f"   {collection['publisher']} — {collection['count']} volumes")
        
        # Étape 1: IDs
        log.info('\n   🔍 Extraction IDs...')
        book_ids = get_book_ids_from_serie(collection['serie_id'])
        log.info(f"      → {len(book_ids)} livres trouvés")
        
        if not book_ids:
            log.warning('      ⚠️ Aucun ID, skip collection')
            continue
        
        await asyncio.sleep(2)
        
        # Étape 2: Sommaires
        log.info('\n   📖 Extraction nouvelles...')
        collection_stories = []
        
        for i, book_id in enumerate(book_ids[:15], 1):  # Test 15 premiers
            log.info(f'\n      [{i}/{min(15,len(book_ids))}] Livre {book_id}')
            
            book_title, stories = await scrape_book_sommaire(book_id)
            
            if book_title and stories:
                log.info(f"         📕 {book_title}")
                log.info(f"         📝 {len(stories)} nouvelles")
                
                for s in stories[:2]:
                    log.info(f"            • {s['author']} : {s['title_vf'][:40]}")
                
                collection_stories.extend(stories)
            
            await asyncio.sleep(random.uniform(2, 4))
        
        log.info(f'\n      → {len(collection_stories)} nouvelles extraites')
        all_stories.extend(collection_stories)
        
        # Étape 3: Matching
        log.info('\n   🔗 Matching DB...')
        matched = 0
        dp_no_vf = []
        
        for s in collection_stories:
            author_last = s['author'].split()[-1] if ' ' in s['author'] else s['author']
            
            sc.execute("""
                SELECT title_id, title, author, goodreads_id, gr_rating, 
                       dp_eu, dp_us, has_french_vf, year
                FROM works
                WHERE author LIKE ?
                AND "type" IN ('short story', 'shortfiction', 'novelette', 'novella')
                ORDER BY annualviews DESC NULLS LAST
                LIMIT 1
            """, (f'%{author_last}%',))
            
            row = sc.fetchone()
            if row:
                matched += 1
                
                # DP sans VF ?
                if row[5] and row[6] and not row[7]:  # dp_eu, dp_us, has_french_vf
                    dp_no_vf.append({
                        'author_vf': s['author'],
                        'title_vf': s['title_vf'],
                        'author_en': row[2],
                        'title_en': row[1],
                        'year': row[8],
                        'gr_rating': row[4],
                        'anthology': s['anthology']
                    })
        
        log.info(f'      → {matched}/{len(collection_stories)} matchées ({100*matched/max(1,len(collection_stories)):.1f}%)')
        
        if dp_no_vf:
            log.info(f'\n   🎯 NOUVELLES DP SANS VF : {len(dp_no_vf)}')
            for m in sorted(dp_no_vf, key=lambda x: float(x.get('gr_rating') or 0), reverse=True)[:10]:
                log.info(f"      • {m['author_vf']} — {m['title_vf']}")
                log.info(f"        EN: {m['title_en']} ({m.get('year')}) | GR:{m.get('gr_rating') or '?'}")
                log.info(f"        Dans: {m['anthology']}")
    
    log.info(f'\n{'='*70}')
    log.info(f'✅ BILAN FINAL')
    log.info(f'   Nouvelles extraites : {len(all_stories)}')
    log.info(f'   Terminé {datetime.now().strftime("%H:%M:%S")}')
    log.info('='*70)
    
    conn.close()

asyncio.run(main())
_lf.close()
