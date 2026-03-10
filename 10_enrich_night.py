"""
10_enrich_night.py
Batch enrichissement synopsis + critiques pour les œuvres DP sans VF.

Sources :
  1. Wikipedia search  → synopsis intro complète (œuvres sans wikipedia_url)
  2. Wikipedia full    → synopsis intro complète (œuvres avec wikipedia_url mais synopsis court)
  3. Open Library      → description + sujets + note/votes

Sécurités :
  - Reprend là où on s'est arrêté (skip si déjà enrichi)
  - Rate limiting respectueux
  - Logs dans /app/data/enrich_night.log
  - Checkpoint toutes les 100 œuvres

Lancer :
  docker exec -d sf-dp-tools python /app/10_enrich_night.py
  # Suivre en direct :
  docker exec sf-dp-tools tail -f /app/data/enrich_night.log
"""
import sqlite3, requests, time, re, json, logging
from datetime import datetime

DB       = '/app/data/sf_dp.sqlite'
LOG_FILE = '/app/data/enrich_night.log'
HEADERS  = {'User-Agent': 'sf-domaine-public/1.0 (public-domain-sf-research)'}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
log = logging.getLogger()

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur  = conn.cursor()

# ── Schema migrations ──────────────────────────────────────────────────────────
for col, defn in [
    ('synopsis_source',  "TEXT"),
    ('ol_description',   "TEXT"),
    ('ol_subjects',      "TEXT"),
    ('ol_rating',        "REAL DEFAULT 0"),
    ('ol_votes',         "INTEGER DEFAULT 0"),
    ('ol_key',           "TEXT"),
    ('wp_searched',      "INTEGER DEFAULT 0"),  # 1 = déjà tenté Wikipedia search
    ('ol_searched',      "INTEGER DEFAULT 0"),  # 1 = déjà tenté OL
]:
    try:
        cur.execute(f'ALTER TABLE works ADD COLUMN {col} {defn}')
        log.info(f'Colonne {col} ajoutée')
    except Exception:
        pass
conn.commit()

# ── Helpers ────────────────────────────────────────────────────────────────────
def clean(text):
    if not text: return ''
    text = re.sub(r'\n{3,}', '\n\n', text.strip())
    text = re.sub(r'\s{3,}', ' ', text)
    return text

def save(every=100, counter=[0]):
    counter[0] += 1
    if counter[0] % every == 0:
        conn.commit()
        log.info(f'  💾 Checkpoint ({counter[0]} ops)')

# ═══════════════════════════════════════════════════════════════════════════════
# ÉTAPE 1 — Wikipedia : œuvres AVEC wikipedia_url mais synopsis court/absent
# ═══════════════════════════════════════════════════════════════════════════════
log.info('=== ÉTAPE 1 : Wikipedia (URL connue, synopsis absent/court) ===')

cur.execute("""
    SELECT title_id, title, author, wikipedia_url
    FROM works
    WHERE (dp_eu=1 OR dp_us=1)
    AND wikipedia_url IS NOT NULL AND wikipedia_url != ''
    AND (synopsis IS NULL OR length(synopsis) < 300)
    AND (wp_searched IS NULL OR wp_searched = 0)
    ORDER BY annualviews DESC NULLS LAST
    LIMIT 2000
""")
rows = list(cur.fetchall())
log.info(f'  {len(rows)} cibles')

ok1 = err1 = 0
for row in rows:
    tid, title, author, wp_url = row['title_id'], row['title'], row['author'], row['wikipedia_url']
    slug = wp_url.rstrip('/').split('/')[-1]
    try:
        r = requests.get('https://en.wikipedia.org/w/api.php', headers=HEADERS, timeout=10, params={
            'action': 'query', 'titles': slug.replace('_', ' '),
            'prop': 'extracts|info', 'exintro': True, 'explaintext': True,
            'redirects': True, 'format': 'json',
        })
        data  = r.json()
        pages = data.get('query', {}).get('pages', {})
        page  = next(iter(pages.values()))
        if page.get('pageid', -1) != -1:
            extract = clean(page.get('extract', ''))
            if extract and len(extract) > 200:
                cur.execute("""UPDATE works SET synopsis=?, synopsis_source='wikipedia_full', wp_searched=1
                               WHERE title_id=?""", (extract[:3000], tid))
                ok1 += 1
            else:
                cur.execute("UPDATE works SET wp_searched=1 WHERE title_id=?", (tid,))
        else:
            cur.execute("UPDATE works SET wp_searched=1 WHERE title_id=?", (tid,))
        save()
    except Exception as e:
        err1 += 1
        if err1 <= 5: log.warning(f'  WP err [{tid}] {title}: {e}')
    time.sleep(0.2)

conn.commit()
log.info(f'  ✅ Étape 1 : {ok1} synopsis, {err1} erreurs')

# ═══════════════════════════════════════════════════════════════════════════════
# ÉTAPE 2 — Wikipedia SEARCH : œuvres SANS wikipedia_url
# ═══════════════════════════════════════════════════════════════════════════════
log.info('\n=== ÉTAPE 2 : Wikipedia search (sans URL connue) ===')

cur.execute("""
    SELECT title_id, title, author
    FROM works
    WHERE (dp_eu=1 OR dp_us=1)
    AND has_french_vf=0
    AND (wikipedia_url IS NULL OR wikipedia_url = '')
    AND (synopsis IS NULL OR length(synopsis) < 200)
    AND (wp_searched IS NULL OR wp_searched = 0)
    ORDER BY annualviews DESC NULLS LAST, award_count DESC
    LIMIT 3000
""")
rows = list(cur.fetchall())
log.info(f'  {len(rows)} cibles')

ok2 = err2 = skip2 = 0
for row in rows:
    tid, title, author = row['title_id'], row['title'], row['author']
    lastname = author.split()[-1] if author else ''
    # Cherche d'abord le titre seul, puis titre + auteur
    found = False
    for q in [f"{title}", f"{title} {lastname}", f"{title} novel"]:
        try:
            r = requests.get('https://en.wikipedia.org/w/api.php', headers=HEADERS, timeout=10, params={
                'action': 'query', 'list': 'search', 'srsearch': q,
                'srlimit': 3, 'format': 'json',
            })
            results = r.json().get('query', {}).get('search', [])
            time.sleep(0.15)

            for res in results:
                # Vérifier que le titre matche bien (éviter les faux positifs)
                res_title = res.get('title', '').lower()
                if title.lower()[:15] not in res_title and title.lower().split()[0] not in res_title:
                    continue

                # Récupérer l'extrait complet
                r2 = requests.get('https://en.wikipedia.org/w/api.php', headers=HEADERS, timeout=10, params={
                    'action': 'query', 'titles': res['title'],
                    'prop': 'extracts|info', 'exintro': True, 'explaintext': True,
                    'redirects': True, 'format': 'json',
                })
                pages = r2.json().get('query', {}).get('pages', {})
                page  = next(iter(pages.values()))
                if page.get('pageid', -1) == -1:
                    continue
                extract = clean(page.get('extract', ''))
                if extract and len(extract) > 200:
                    wp_url = f"https://en.wikipedia.org/wiki/{res['title'].replace(' ', '_')}"
                    cur.execute("""
                        UPDATE works SET synopsis=?, synopsis_source='wikipedia_search',
                               wikipedia_url=?, wp_searched=1
                        WHERE title_id=?
                    """, (extract[:3000], wp_url, tid))
                    ok2 += 1
                    found = True
                    save()
                    time.sleep(0.2)
                    break
            if found:
                break
        except Exception as e:
            err2 += 1
            if err2 <= 5: log.warning(f'  WP search err [{tid}] {title}: {e}')
            break

    if not found:
        cur.execute("UPDATE works SET wp_searched=1 WHERE title_id=?", (tid,))
        skip2 += 1
        save()
    time.sleep(0.15)

conn.commit()
log.info(f'  ✅ Étape 2 : {ok2} trouvés, {skip2} non trouvés, {err2} erreurs')

# ═══════════════════════════════════════════════════════════════════════════════
# ÉTAPE 3 — Open Library : description + sujets enrichis + note/votes
# ═══════════════════════════════════════════════════════════════════════════════
log.info('\n=== ÉTAPE 3 : Open Library ===')

cur.execute("""
    SELECT title_id, title, author, goodreads_id
    FROM works
    WHERE (dp_eu=1 OR dp_us=1)
    AND has_french_vf=0
    AND (ol_searched IS NULL OR ol_searched = 0)
    ORDER BY annualviews DESC NULLS LAST, award_count DESC
    LIMIT 5000
""")
rows = list(cur.fetchall())
log.info(f'  {len(rows)} cibles')

ok3 = err3 = 0
for row in rows:
    tid, title, author = row['title_id'], row['title'], row['author']
    try:
        r = requests.get('https://openlibrary.org/search.json', headers=HEADERS, timeout=10,
                         params={'title': title, 'author': author, 'limit': 3, 'fields':
                                 'key,title,author_name,first_publish_year,edition_count,'
                                 'ratings_average,ratings_count,subject,description'})
        docs = r.json().get('docs', [])

        matched = None
        for d in docs:
            # Vérifier que le titre est proche
            dt = d.get('title', '').lower()
            if title.lower()[:10] in dt or dt[:10] in title.lower()[:15]:
                matched = d
                break

        if matched:
            ol_key     = matched.get('key', '')
            ol_rating  = matched.get('ratings_average')
            ol_votes   = matched.get('ratings_count', 0)
            ol_subj    = ', '.join(matched.get('subject', [])[:20])

            # Description longue via /works/OLXXXXW.json
            ol_desc = ''
            if ol_key:
                try:
                    rw = requests.get(f'https://openlibrary.org{ol_key}.json',
                                      headers=HEADERS, timeout=8)
                    wdata = rw.json()
                    desc = wdata.get('description', '')
                    if isinstance(desc, dict): desc = desc.get('value', '')
                    ol_desc = clean(str(desc))[:2000] if desc else ''
                    time.sleep(0.2)
                except Exception:
                    pass

            cur.execute("""
                UPDATE works SET
                    ol_description = ?,
                    ol_subjects    = ?,
                    ol_rating      = ?,
                    ol_votes       = ?,
                    ol_key         = ?,
                    ol_searched    = 1
                WHERE title_id = ?
            """, (ol_desc or None, ol_subj or None,
                  round(ol_rating, 2) if ol_rating else None,
                  ol_votes or 0, ol_key or None, tid))
            ok3 += 1
        else:
            cur.execute("UPDATE works SET ol_searched=1 WHERE title_id=?", (tid,))

        save()
        time.sleep(0.25)

    except Exception as e:
        err3 += 1
        cur.execute("UPDATE works SET ol_searched=1 WHERE title_id=?", (tid,))
        if err3 <= 5: log.warning(f'  OL err [{tid}] {title}: {e}')
        time.sleep(0.5)

conn.commit()
log.info(f'  ✅ Étape 3 : {ok3} enrichis, {err3} erreurs')

# ═══════════════════════════════════════════════════════════════════════════════
# STATS FINALES
# ═══════════════════════════════════════════════════════════════════════════════
log.info('\n=== STATS FINALES ===')
for label, sql in [
    ("Synopsis total",               "SELECT COUNT(*) FROM works WHERE synopsis IS NOT NULL AND synopsis!=''"),
    ("Synopsis isfdb",               "SELECT COUNT(*) FROM works WHERE synopsis_source='isfdb'"),
    ("Synopsis wikipedia_full",      "SELECT COUNT(*) FROM works WHERE synopsis_source='wikipedia_full'"),
    ("Synopsis wikipedia_search",    "SELECT COUNT(*) FROM works WHERE synopsis_source='wikipedia_search'"),
    ("OL description",               "SELECT COUNT(*) FROM works WHERE ol_description IS NOT NULL AND ol_description!=''"),
    ("OL rating",                    "SELECT COUNT(*) FROM works WHERE ol_rating > 0"),
    ("OL sujets",                    "SELECT COUNT(*) FROM works WHERE ol_subjects IS NOT NULL"),
]:
    cur.execute(sql)
    log.info(f'  {label:40s}: {cur.fetchone()[0]}')

log.info(f'\n✅ Terminé à {datetime.now().strftime("%H:%M:%S")}')
conn.close()
