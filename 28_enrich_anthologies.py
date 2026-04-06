"""
28_enrich_anthologies.py
Enrichit contents_json des anthologies de référence depuis MariaDB ISFDB.
"""
import sqlite3, json, logging, mysql.connector
from datetime import datetime

DB = '/app/data/sf_dp.sqlite'
LOG_FILE = '/app/data/28_anthologies.log'

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()])
log = logging.getLogger()
log.info('=== 28_enrich_anthologies.py ===')

conn = sqlite3.connect(DB, timeout=60)
conn.row_factory = sqlite3.Row
sc = conn.cursor()

# Liste COMPLÈTE des anthologies de référence Goodreads
REFERENCE_ANTHOLOGIES = [
    # Top tier (Hall of Fame, Dangerous Visions)
    'Science Fiction Hall of Fame',
    'Dangerous Visions',
    'Again, Dangerous Visions',
    
    # Best of year (Gardner Dozois, etc.)
    'Year\'s Best Science Fiction',
    'Best Science Fiction of the Year',
    'World\'s Best Science Fiction',
    
    # Hugo/Nebula compilations
    'Hugo Winners',
    'Nebula Award',
    'Best of the Nebulas',
    
    # Classiques historiques
    'Adventures in Time and Space',
    'Treasury of Science Fiction',
    'Ascent of Wonder',
    'The Good Old Stuff',
    
    # Penguin/Oxford/Norton prestige
    'Penguin Science Fiction',
    'Oxford Book of Science Fiction',
    'Norton Book of Science Fiction',
    
    # Thématiques classiques
    'Before the Golden Age',
    'Science Fiction of the 30\'s',
    'Mammoth Book of Golden Age',
    'Classic Science Fiction',
    
    # Anthologies femmes/diversité
    'Women of Wonder',
    'Future Is Female',
    'Sisters of the Revolution',
    
    # Space opera & hard SF
    'Space Opera Renaissance',
    'Good New Stuff',
    'Hard SF Renaissance',
    
    # Éditeurs célèbres
    'Worlds of Wonder',
    'Mirror of Infinity',
    'World Treasury of Science Fiction',
    'Big Book of Science Fiction',
    
    # Autres références majeures
    'Brave New Worlds',
    'Wastelands',
    'Mirrorshades',
    'Rewired',
    'New Space Opera',
    'Wesleyan Anthology',
    
    # Star SF & collections Pohl
    'Star Science Fiction Stories',
    
    # Groff Conklin (anthologiste majeur)
    'Treasury of Science Fiction',
    'Great Stories of Space Travel',
    'Science Fiction Terror Tales',
    
    # Isaac Asimov anthologies
    '50 Short Science Fiction Tales',
    '100 Great Science Fiction',
    'Microcosmic Tales',
    
    # VanderMeer
    'Time Traveler\'s Almanac',
    
    # Jonathan Strahan (éditeur prolifique)
    'Engineering Infinity',
    'Edge of Infinity',
    'Reach for Infinity',
    'Meeting Infinity',
    
    # John Joseph Adams
    'Other Worlds Than These',
    'Federations',
    'Armored',
]

# Trouver TOUTES les anthologies correspondantes dans SQLite
log.info('Recherche anthologies de référence...')
found_anthologies = []

for ref in REFERENCE_ANTHOLOGIES:
    sc.execute("""
        SELECT title_id, title, year, contents_json IS NOT NULL as has_contents
        FROM works
        WHERE title LIKE ?
        AND "type" IN ('anthology', 'collection')
    """, (f'%{ref}%',))
    
    for r in sc.fetchall():
        found_anthologies.append(r)

log.info(f'{len(found_anthologies)} anthologies trouvées')

# Stats avant enrichissement
already_filled = sum(1 for a in found_anthologies if a['has_contents'])
to_enrich = len(found_anthologies) - already_filled
log.info(f'  Déjà rempli: {already_filled}')
log.info(f'  À enrichir: {to_enrich}')

# Échantillon
log.info('\nÉchantillon anthologies trouvées:')
for a in found_anthologies[:20]:
    status = '✅' if a['has_contents'] else '❌'
    log.info(f'  {status} [{a["year"] or "?"}] {a["title"][:60]}')

# Connecter MariaDB
log.info('\nConnexion MariaDB ISFDB...')
try:
    mc_conn = mysql.connector.connect(
        host='mariadb-sfdb', port=3306,
        user='root', password='isfdb', database='isfdb',
        connection_timeout=10)
    mc = mc_conn.cursor(dictionary=True)
    log.info('✅ Connecté MariaDB')
except Exception as e:
    log.error(f'❌ Échec connexion MariaDB: {e}')
    conn.close()
    exit(1)

# Enrichir chaque anthologie
enriched = 0
skipped = 0
not_found = 0

for antho in found_anthologies:
    tid = antho['title_id']
    title = antho['title']
    
    # Skip si déjà rempli
    if antho['has_contents']:
        skipped += 1
        continue
    
    # Chercher dans ISFDB par titre exact
    mc.execute("""
        SELECT t.title_id
        FROM titles t
        WHERE t.title_title = %s
        AND t.title_ttype IN ('ANTHOLOGY', 'COLLECTION')
        LIMIT 1
    """, (title,))
    
    isfdb_title = mc.fetchone()
    if not isfdb_title:
        not_found += 1
        continue
    
    isfdb_tid = isfdb_title['title_id']
    
    # Récupérer contenus via pub_content
    # Stratégie : trouver publications de cette anthologie, puis leurs contenus
    mc.execute("""
        SELECT DISTINCT ct.title_id, ct.title_title, ct.title_ttype,
               a.author_canonical
        FROM titles t
        JOIN pubs p ON p.pub_title = t.title_title
        JOIN pub_content pc ON pc.pub_id = p.pub_id
        JOIN titles ct ON ct.title_id = pc.title_id
        LEFT JOIN canonical_author ca ON ca.title_id = ct.title_id
        LEFT JOIN authors a ON a.author_id = ca.author_id
        WHERE t.title_id = %s
        AND ct.title_ttype IN ('SHORTFICTION', 'NOVELETTE', 'NOVELLA', 'ESSAY', 'POEM')
        ORDER BY ct.title_title
        LIMIT 200
    """, (isfdb_tid,))
    
    contents = []
    for story in mc.fetchall():
        contents.append({
            'title_id': story['title_id'],
            'title': story['title_title'],
            'author': story['author_canonical'],
            'type': story['title_ttype'].lower() if story['title_ttype'] else 'unknown'
        })
    
    if contents:
        # Mettre à jour SQLite
        sc.execute("""
            UPDATE works
            SET contents_json = ?
            WHERE title_id = ?
        """, (json.dumps(contents), tid))
        
        enriched += 1
        log.info(f'✅ [{antho["year"] or "?"}] {title[:50]} → {len(contents)} contenus')
        
        # Commit tous les 10
        if enriched % 10 == 0:
            conn.commit()

conn.commit()
mc_conn.close()
conn.close()

log.info(f'\n=== RÉSULTATS ===')
log.info(f'Total anthologies: {len(found_anthologies)}')
log.info(f'Enrichies: {enriched}')
log.info(f'Déjà rempli: {skipped}')
log.info(f'Non trouvées ISFDB: {not_found}')
log.info(f'\n✅ TERMINÉ {datetime.now().strftime("%H:%M:%S")}')
