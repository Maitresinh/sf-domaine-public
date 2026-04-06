"""
31_histoires_de.py
Extrait nouvelles de "Histoires de..." (Livre de Poche, 1974-1985)
Série noosfere 2704 - 36 volumes thématiques
"""
import fcntl, sys
_lf = open("/app/data/31h.lock", "w")
try:
    fcntl.flock(_lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
except IOError:
    print("Instance deja en cours. Abandon."); sys.exit(0)

import sqlite3, logging, asyncio, re, random
from crawl4ai import AsyncWebCrawler
from datetime import datetime

DB = '/app/data/sf_dp.sqlite'
LOG_FILE = '/app/data/31_histoires.log'

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()])
log = logging.getLogger()

# URLs directes des 36 volumes "Histoires de..."
# Format: (numéro, titre, année, numlivre)
HISTOIRES_DE = [
    (1, "Histoires d'extraterrestres", 1974, 'niourf.asp?numlivre='),  # Ajouter IDs
    (2, "Histoires de robots", 1974, ''),
    (3, "Histoires de cosmonautes", 1974, ''),
    # ... À compléter
]

# Pour l'instant, scraping générique sur la série
SERIE_URL = 'https://www.noosfere.org/livres/serie.asp?numserie=2704'

async def get_book_ids_from_serie():
    """Extrait IDs de tous les livres de la série."""
    import requests
    from bs4 import BeautifulSoup
    
    r = requests.get(SERIE_URL, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
    soup = BeautifulSoup(r.text, 'html.parser')
    
    book_ids = []
    for link in soup.find_all('a', href=lambda x: x and 'numlivre=' in x):
        match = re.search(r'numlivre=(\d+)', link['href'])
        if match:
            book_ids.append(match.group(1))
    
    return list(set(book_ids))

async def scrape_book_sommaire(numlivre):
    """Extrait sommaire d'un livre noosfere."""
    url = f'https://www.noosfere.org/livres/niourf.asp?numlivre={numlivre}'
    
    async with AsyncWebCrawler(verbose=False) as crawler:
        result = await crawler.arun(url=url, word_count_threshold=10)
        
        if not result.success:
            return None, []
        
        html = result.html or ""
        
        # Titre
        title_match = re.search(r'<title>([^<]+?)\s*-\s*noosfere', html, re.IGNORECASE)
        book_title = title_match.group(1).strip() if title_match else f"Livre {numlivre}"
        
        stories = []
        
        # Chercher sommaire/contenu
        # Pattern noosfere: lignes avec auteur, «titre»
        lines = html.split('\n')
        
        for line in lines:
            # Pattern: Nom Prénom, «Titre de la nouvelle»
            match = re.search(r'([A-Z][\w\s\-\'\.]+?)\s*,\s*[«"]([^»"]{5,100})[»"]', line)
            if match:
                author_raw = match.group(1).strip()
                title = match.group(2).strip()
                
                # Nettoyer auteur
                author = re.sub(r'\s*\([^\)]+\)', '', author_raw)
                
                # Filtrer intro/préface
                if not any(x in title.lower() for x in ['introduction', 'préface', 'postface', 'note']):
                    stories.append({
                        'author': author,
                        'title_vf': title,
                        'anthology': book_title
                    })
        
        return book_title, stories

async def main():
    log.info('=== 31_histoires_de.py ===')
    log.info('Collection "Histoires de..." (Livre de Poche, 1974-1985)')
    
    conn = sqlite3.connect(DB, timeout=60)
    sc = conn.cursor()
    
    # Étape 1: Liste IDs
    log.info('\n📚 Extraction IDs livres série 2704...')
    try:
        book_ids = await get_book_ids_from_serie()
        log.info(f'   {len(book_ids)} volumes trouvés')
    except Exception as e:
        log.error(f'   Erreur: {e}')
        book_ids = []
    
    if not book_ids:
        log.warning('   Aucun livre trouvé, abandon')
        return
    
    # Étape 2: Scrape chaque livre
    log.info('\n📖 Extraction nouvelles...')
    
    all_stories = []
    
    for i, book_id in enumerate(book_ids[:10], 1):  # Test sur 10
        log.info(f'\n   [{i}/{min(10, len(book_ids))}] Livre {book_id}')
        
        book_title, stories = await scrape_book_sommaire(book_id)
        
        if book_title:
            log.info(f'      📕 {book_title}')
            log.info(f'      📝 {len(stories)} nouvelles')
            
            for s in stories[:3]:
                log.info(f"         • {s['author']} : {s['title_vf']}")
            
            all_stories.extend(stories)
        
        await asyncio.sleep(random.uniform(2, 4))
    
    log.info(f'\n   → Total : {len(all_stories)} nouvelles extraites')
    
    # Étape 3: Matching DB
    log.info('\n🔗 Matching avec DB...')
    
    matched = 0
    for s in all_stories:
        author_last = s['author'].split()[-1] if s['author'] else ''
        
        sc.execute("""
            SELECT title_id, title, author, goodreads_id, gr_rating, dp_eu, dp_us, has_french_vf
            FROM works
            WHERE author LIKE ?
            AND "type" IN ('short story', 'shortfiction', 'novelette', 'novella')
            LIMIT 1
        """, (f'%{author_last}%',))
        
        row = sc.fetchone()
        if row:
            matched += 1
            log.info(f"   ✓ {s['author']} — {s['title_vf']}")
            log.info(f"     → {row[2]} — {row[1]} (GR:{row[4] or '?'})")
    
    log.info(f'\n   {matched}/{len(all_stories)} matchées ({100*matched/max(1,len(all_stories)):.1f}%)')
    
    log.info(f'\n✅ Terminé {datetime.now().strftime("%H:%M:%S")}')
    conn.close()

asyncio.run(main())
_lf.close()
