"""
29_anthology_reviews_v2.py
Scrape reviews Goodreads des anthologies pour extraire synopsis nouvelles.

Stratégie :
1. Anthologies avec GR + contents_json
2. Fetch page GR anthologie + reviews
3. Parser reviews pour extraire mentions nouvelles
4. Extraire contexte (synopsis) autour du titre
5. Enrichir colonne synopsis des nouvelles
"""
import sqlite3, json, logging, asyncio, re
from datetime import datetime
from crawl4ai import AsyncWebCrawler

DB = '/app/data/sf_dp.sqlite'
LOG_FILE = '/app/data/29_anthology_reviews.log'

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()])
log = logging.getLogger()
log.info('=== 29_anthology_reviews_v2.py ===')

# Lock file
import fcntl, sys
_lf = open("/app/data/29.lock", "w")
try:
    fcntl.flock(_lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
except IOError:
    print("Instance déjà en cours. Abandon.")
    sys.exit(0)

conn = sqlite3.connect(DB, timeout=60)
conn.row_factory = sqlite3.Row
sc = conn.cursor()

# Anthologies prioritaires avec GR + contenus
log.info('Extraction anthologies prioritaires...')
sc.execute("""
    SELECT w.title_id, w.title, w.goodreads_id, w.contents_json, w.year
    FROM works w
    WHERE w."type" IN ('anthology', 'collection')
    AND w.goodreads_id IS NOT NULL
    AND w.contents_json IS NOT NULL
    AND (
        w.title LIKE '%Hall of Fame%'
        OR w.title LIKE '%Best%'
        OR w.title LIKE '%Dangerous Visions%'
        OR w.title LIKE '%Year''s Best%'
        OR w.title LIKE '%Hugo%'
        OR w.title LIKE '%Nebula%'
        OR w.title LIKE '%Treasury%'
        OR w.title LIKE '%Masterpiece%'
        OR w.title LIKE '%Classic%'
    )
    ORDER BY w.year DESC
""")

anthologies = list(sc.fetchall())
log.info(f'{len(anthologies)} anthologies prioritaires trouvées')

# Afficher échantillon
log.info('\nÉchantillon :')
for a in anthologies[:10]:
    contents = json.loads(a['contents_json'])
    log.info(f'  [{a["year"]}] {a["title"][:50]} ({len(contents)} nouvelles)')

async def extract_story_synopses(antho):
    """
    Scrape page + reviews anthologie GR.
    Extraire synopsis nouvelles depuis reviews.
    """
    gr_id = antho['goodreads_id']
    url = f"https://www.goodreads.com/book/show/{gr_id}"
    
    try:
        async with AsyncWebCrawler(verbose=False) as crawler:
            # Fetch page principale
            result = await crawler.arun(
                url=url,
                word_count_threshold=10,
                bypass_cache=True,
                wait_for="css:.reviewText"
            )
            
            if not result.success:
                log.warning(f'Échec fetch {antho["title"][:40]}')
                return {}
            
            text = result.markdown or ""
            
            # Parser contents_json
            contents = json.loads(antho['contents_json'])
            story_synopses = {}
            
            # Pour chaque nouvelle, chercher mentions dans reviews
            for story in contents:
                story_title = story['title']
                story_author = story.get('author', '')
                
                # Patterns de recherche
                # 1. "Story Title" by Author - description
                # 2. Story Title: description
                # 3. mentions dans paragraphes reviews
                
                # Chercher toutes les occurrences du titre
                pattern = re.escape(story_title)
                matches = list(re.finditer(pattern, text, re.IGNORECASE))
                
                if not matches:
                    continue
                
                best_synopsis = None
                max_score = 0
                
                for match in matches:
                    start = match.start()
                    
                    # Extraire contexte (500 chars après le titre)
                    context_end = min(len(text), start + 500)
                    context = text[start:context_end]
                    
                    # Scorer le contexte
                    score = 0
                    
                    # Bonus si contient mots-clés synopsis
                    synopsis_kw = ['story', 'about', 'follows', 'tells', 'explores', 
                                   'depicts', 'centers', 'focuses', 'set in', 'features']
                    for kw in synopsis_kw:
                        if kw in context.lower():
                            score += 1
                    
                    # Bonus si mentionne l'auteur
                    if story_author and story_author.lower() in context.lower():
                        score += 2
                    
                    # Bonus si commence par patterns typiques
                    if re.match(r'^["\']?[\w\s]+["\']?\s+(by|—|-)\s+', context):
                        score += 3
                    
                    # Pénalité si trop court
                    if len(context) < 100:
                        score -= 2
                    
                    if score > max_score:
                        max_score = score
                        # Nettoyer contexte
                        clean = re.sub(r'\s+', ' ', context)
                        clean = clean.strip()
                        best_synopsis = clean[:500]
                
                if best_synopsis and max_score >= 2:
                    story_synopses[story_title] = {
                        'synopsis': best_synopsis,
                        'author': story_author,
                        'score': max_score
                    }
            
            return story_synopses
            
    except Exception as e:
        log.warning(f'Erreur scraping {antho["title"][:40]}: {e}')
        return {}

async def process_anthologies():
    """Traiter toutes les anthologies prioritaires"""
    total_enriched = 0
    
    for i, antho in enumerate(anthologies[:100], 1):  # Top 100
        log.info(f'\n[{i}/{min(100, len(anthologies))}] {antho["title"][:50]}')
        
        synopses = await extract_story_synopses(antho)
        
        if not synopses:
            log.info(f'  ⚠️  Aucun synopsis extrait')
            continue
        
        log.info(f'  ✅ {len(synopses)} synopsis extraits')
        
        # Enrichir DB
        contents = json.loads(antho['contents_json'])
        for story in contents:
            story_title = story['title']
            
            if story_title not in synopses:
                continue
            
            syn_data = synopses[story_title]
            
            # Chercher nouvelle dans DB
            sc.execute("""
                SELECT title_id, synopsis, author
                FROM works
                WHERE title = ?
                LIMIT 1
            """, (story_title,))
            
            work = sc.fetchone()
            
            if not work:
                # Essayer match fuzzy par auteur
                if syn_data['author']:
                    sc.execute("""
                        SELECT title_id, synopsis, author
                        FROM works
                        WHERE title = ?
                        AND author LIKE ?
                        LIMIT 1
                    """, (story_title, f"%{syn_data['author'][:10]}%"))
                    work = sc.fetchone()
            
            if work and (not work['synopsis'] or len(work['synopsis']) < 100):
                # Enrichir synopsis
                source = f"anthology_review:{antho['title']}"
                
                sc.execute("""
                    UPDATE works
                    SET synopsis = ?,
                        synopsis_source = ?
                    WHERE title_id = ?
                """, (syn_data['synopsis'], source, work['title_id']))
                
                total_enriched += 1
                log.info(f'    → {story_title[:40]} enrichi (score={syn_data["score"]})')
        
        # Commit tous les 10
        if i % 10 == 0:
            conn.commit()
            log.info(f'\n💾 Commit après {i} anthologies ({total_enriched} nouvelles enrichies)')
        
        # Rate limiting
        await asyncio.sleep(8)
    
    return total_enriched

# Lancer
log.info('\n=== DÉBUT SCRAPING ===')
enriched = asyncio.run(process_anthologies())

conn.commit()
conn.close()
_lf.close()

log.info(f'\n=== RÉSULTATS ===')
log.info(f'Anthologies traitées: {min(100, len(anthologies))}')
log.info(f'Nouvelles enrichies: {enriched}')
log.info(f'\n✅ TERMINÉ {datetime.now().strftime("%H:%M:%S")}')
