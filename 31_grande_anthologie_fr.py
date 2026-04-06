"""
31_grande_anthologie_fr.py
Scrape "La Grande Anthologie de la SF" + "Les meilleurs récits de..."
Extrait nouvelles depuis noosfere puis enrichit avec Goodreads.
"""
import fcntl, sys
_lf = open("/app/data/31.lock", "w")
try:
    fcntl.flock(_lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
except IOError:
    print("Instance deja en cours. Abandon."); sys.exit(0)

import sqlite3, logging, asyncio, re, random
from crawl4ai import AsyncWebCrawler
from datetime import datetime

DB = '/app/data/sf_dp.sqlite'
LOG_FILE = '/app/data/31_grande_anthologie.log'

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()])
log = logging.getLogger()

# Collections FR majeures
COLLECTIONS = [
    {
        'name': 'La Grande Anthologie de la Science-Fiction',
        'url': 'https://www.noosfere.org/livres/serie.asp?numserie=2704',
        'publisher': 'Livre de Poche',
        'years': '1966-1985',
        'note': 'Collection historique dirigée par Jacques Goimard'
    },
    {
        'name': 'Les meilleurs récits de...',
        'url': 'https://www.noosfere.org/livres/serie.asp?numserie=410',
        'publisher': 'Presses Pocket/J\'ai Lu',
        'years': '1973-1983',
        'note': 'Recueils par magazine (Weird Tales, Astounding, Galaxy, etc.)'
    }
]

async def scrape_collection_books(url):
    """Liste tous les livres d'une collection."""
    async with AsyncWebCrawler(verbose=False) as crawler:
        result = await crawler.arun(url=url, word_count_threshold=10)
        
        if not result.success:
            return []
        
        html = result.html or ""
        
        # Extraire IDs livres
        book_ids = re.findall(r'numlivre=(\d+)', html)
        urls = [f'https://www.noosfere.org/livres/niourf.asp?numlivre={bid}' 
                for bid in set(book_ids)]
        
        return urls

async def scrape_book_contents(url):
    """Extrait contenu d'une anthologie."""
    async with AsyncWebCrawler(verbose=False) as crawler:
        result = await crawler.arun(url=url, word_count_threshold=10)
        
        if not result.success:
            return None, []
        
        html = result.html or ""
        
        # Titre anthologie
        title_match = re.search(r'<title>([^<]+)</title>', html)
        book_title = title_match.group(1).strip() if title_match else "?"
        book_title = re.sub(r'\s*-\s*noosfere', '', book_title)
        
        stories = []
        
        # Chercher section sommaire/contenu
        sommaire_section = re.search(r'Sommaire|Contenu(.*?)(?:Notes|Critiques|$)', html, re.DOTALL | re.IGNORECASE)
        if sommaire_section:
            content = sommaire_section.group(1)
        else:
            content = html
        
        # Pattern : Auteur + titre entre guillemets
        # Ex: "Robert Heinlein, «Les Vertes collines de la Terre»"
        for match in re.finditer(r'([A-Z][\w\s\-\.\'\,]+?)\s*[,:]?\s*[«"]([^»"]{5,80})[»"]', content):
            author = match.group(1).strip()
            title = match.group(2).strip()
            
            # Nettoyer auteur (enlever prénoms en trop)
            author = re.sub(r'\s+\([^\)]+\)', '', author)
            author = author.split(',')[0].strip()
            
            # Filtrer faux positifs
            if len(title) >= 5 and len(author) >= 3 and not any(x in title.lower() for x in ['introduction', 'préface', 'postface']):
                stories.append({
                    'author': author,
                    'title_vf': title,
                    'anthology': book_title
                })
        
        return book_title, stories

async def match_with_db(conn, stories):
    """Matche nouvelles avec DB."""
    sc = conn.cursor()
    matched = []
    
    for s in stories:
        # Recherche floue par auteur
        author_cleaned = s['author'].split()[-1]  # Nom de famille
        
        sc.execute("""
            SELECT title_id, title, author, goodreads_id, gr_rating, 
                   dp_eu, dp_us, has_french_vf, year
            FROM works
            WHERE author LIKE ?
            AND "type" IN ('short story', 'shortfiction', 'novelette', 'novella')
            ORDER BY annualviews DESC NULLS LAST
            LIMIT 5
        """, (f'%{author_cleaned}%',))
        
        rows = sc.fetchall()
        if rows:
            # Prendre la plus connue de l'auteur
            best = rows[0]
            matched.append({
                **s,
                'title_id': best[0],
                'title_en': best[1],
                'author_en': best[2],
                'goodreads_id': best[3],
                'gr_rating': best[4],
                'dp_eu': best[5],
                'dp_us': best[6],
                'has_vf': best[7],
                'year': best[8]
            })
    
    return matched

async def main():
    log.info('=== 31_grande_anthologie_fr.py ===')
    
    conn = sqlite3.connect(DB, timeout=60)
    
    all_stories = []
    all_matched = []
    
    for collection in COLLECTIONS:
        log.info(f"\n{'='*70}")
        log.info(f"📚 {collection['name']}")
        log.info(f"   Éditeur : {collection['publisher']}")
        log.info(f"   Période : {collection['years']}")
        log.info(f"   Note    : {collection['note']}")
        log.info('='*70)
        
        # Liste livres
        log.info('\n🔍 Étape 1 : Liste des anthologies...')
        book_urls = await scrape_collection_books(collection['url'])
        log.info(f'   → {len(book_urls)} anthologies trouvées')
        
        await asyncio.sleep(2)
        
        # Contenu de chaque anthologie
        log.info('\n📖 Étape 2 : Extraction des nouvelles...')
        collection_stories = []
        
        for i, url in enumerate(book_urls[:10], 1):  # Limiter à 10 pour test
            log.info(f'\n   [{i}/{min(10, len(book_urls))}] {url}')
            
            book_title, stories = await scrape_book_contents(url)
            log.info(f'      📕 {book_title}')
            log.info(f'      📝 {len(stories)} nouvelles extraites')
            
            if stories:
                for s in stories[:3]:
                    log.info(f"         - {s['author']} : {s['title_vf']}")
            
            collection_stories.extend(stories)
            all_stories.extend(stories)
            
            await asyncio.sleep(random.uniform(2, 4))
        
        log.info(f'\n   → Total collection : {len(collection_stories)} nouvelles')
        
        # Matching DB
        log.info('\n🔗 Étape 3 : Matching avec DB...')
        matched = await match_with_db(conn, collection_stories)
        log.info(f'   → {len(matched)}/{len(collection_stories)} matchées ({100*len(matched)/max(1,len(collection_stories)):.1f}%)')
        
        all_matched.extend(matched)
        
        # Stats intéressantes
        dp_matches = [m for m in matched if m.get('dp_eu') and m.get('dp_us')]
        dp_no_vf = [m for m in dp_matches if not m.get('has_vf')]
        
        log.info(f'\n   📊 Stats :')
        log.info(f'      DP (EU+US)        : {len(dp_matches)}')
        log.info(f'      DP sans VF        : {len(dp_no_vf)}')
        log.info(f'      Avec Goodreads ID : {len([m for m in matched if m.get("goodreads_id")])}')
        
        if dp_no_vf:
            log.info(f'\n   🎯 TOP NOUVELLES DP SANS VF :')
            for m in sorted(dp_no_vf, key=lambda x: float(x.get('gr_rating') or 0), reverse=True)[:10]:
                log.info(f"      - {m['author']} — {m['title_vf']}")
                log.info(f"        EN: {m['title_en']} ({m.get('year')})")
                log.info(f"        GR: {m.get('gr_rating') or '?'} | ID: {m.get('goodreads_id') or 'manquant'}")
    
    log.info(f'\n{'='*70}')
    log.info(f'✅ RÉSUMÉ FINAL')
    log.info(f'   Total nouvelles extraites : {len(all_stories)}')
    log.info(f'   Total matchées avec DB    : {len(all_matched)}')
    log.info(f'   Taux de matching          : {100*len(all_matched)/max(1,len(all_stories)):.1f}%')
    log.info(f'⏰ Terminé à {datetime.now().strftime("%H:%M:%S")}')
    log.info('='*70)
    
    conn.close()

asyncio.run(main())
_lf.close()
