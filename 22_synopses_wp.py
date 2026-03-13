
"""
22_synopses_wp.py
Batch complet — complétion synopses via Wikipedia API.

Stratégie :
  1. Recherche Wikipedia API opensearch : "{title} {lastname} novel/story"
  2. Validation stricte :
     - Pas de page de désambiguïsation
     - Nom de l'auteur présent dans le texte
     - Au moins un mot du titre présent
  3. Extraction premier paragraphe substantiel

Priorité :
  1. DP EU ou US + sans VF + primés
  2. DP EU ou US + sans VF + score élevé (annualviews + nb_langues_vf)
  3. DP EU ou US + sans VF

Pas de LIMIT — tourne jusqu'au bout (~27h pour 48 000 cibles).
Checkpoint toutes les 500 œuvres. Reprend là où on s'est arrêté.

Lancer :
  docker exec -d sf-dp-tools python3 /app/22_synopses_wp.py
  docker exec sf-dp-tools tail -f /app/data/22_synopses_wp.log
"""
import fcntl, sys
_lf = open("/app/data/22.lock", "w")
try:
    fcntl.flock(_lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
except IOError:
    print("Instance déjà en cours. Abandon.")
    sys.exit(0)

import sqlite3, requests, time, logging, re, unicodedata
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
DB       = '/app/data/sf_dp.sqlite'
LOG_FILE = '/app/data/22_synopses_wp.log'
WAIT     = 1.5     # secondes entre requêtes API Wikipedia
MIN_LEN  = 80      # caractères minimum pour accepter un synopsis
COMMIT_N = 500     # checkpoint tous les N traités

HEADERS = {'User-Agent': 'sf-domaine-public/1.0 (public-domain-sf-research)'}

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)-7s %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
log = logging.getLogger()
log.info(f'=== 22_synopses_wp.py — {datetime.now().strftime("%Y-%m-%d %H:%M")} ===')

# ── DB ────────────────────────────────────────────────────────────────────────
conn = sqlite3.connect(DB, timeout=60)
conn.row_factory = sqlite3.Row
cur  = conn.cursor()

# ── Helpers ───────────────────────────────────────────────────────────────────
def normalize(s):
    if not s: return ''
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return s.lower().strip()

def lastname(author):
    if not author: return ''
    parts = str(author).strip().split()
    return parts[-1] if parts else ''

def is_disambiguation(text):
    markers = ['may refer to:', 'can refer to:', 'refer to any of',
               'is a disambiguation', 'the following meanings']
    t = text.lower()
    return any(m in t for m in markers)

def extract_intro(text):
    paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
    for p in paragraphs:
        if len(p) < MIN_LEN: continue
        if p.startswith('=='): continue
        if p.lower().startswith(('see also', 'references', 'external')): continue
        p = re.sub(r'\[\d+\]', '', p)
        p = re.sub(r'\s{2,}', ' ', p)
        return p.strip()
    return None

def validate(text, title, author):
    if not text or len(text) < MIN_LEN:
        return False, 'texte trop court'
    if is_disambiguation(text):
        return False, 'désambiguïsation'
    t = normalize(text)
    ln = normalize(lastname(author))
    if ln and len(ln) > 2 and ln not in t:
        return False, f'auteur "{ln}" absent'
    title_words = [normalize(w) for w in str(title).split() if len(w) > 3]
    if title_words and not any(w in t for w in title_words):
        return False, 'titre absent'
    return True, 'ok'

def wp_fetch_extract(wp_title):
    """Récupère l'intro Wikipedia d'un article par son titre exact."""
    r = requests.get(
        'https://en.wikipedia.org/w/api.php',
        params={
            'action': 'query',
            'titles': wp_title,
            'prop': 'extracts',
            'exintro': True,
            'explaintext': True,
            'format': 'json'
        },
        headers=HEADERS,
        timeout=8
    )
    r.raise_for_status()
    pages = r.json().get('query', {}).get('pages', {})
    for page in pages.values():
        return page.get('extract', '')
    return ''

def wp_search(title, author, work_type=''):
    """
    Cherche un synopsis Wikipedia pour une œuvre.
    Retourne (synopsis, url) ou (None, None).
    """
    type_hint = 'novel' if 'NOVEL' in str(work_type).upper() else 'story'
    ln = lastname(author)

    queries = [
        f'{title} {ln} {type_hint}',
        f'{title} {ln}',
        f'{title} science fiction',
    ]

    for query in queries:
        try:
            r = requests.get(
                'https://en.wikipedia.org/w/api.php',
                params={
                    'action': 'opensearch',
                    'search': query,
                    'limit': 3,
                    'namespace': 0,
                    'format': 'json'
                },
                headers=HEADERS,
                timeout=8
            )
            r.raise_for_status()
            data = r.json()
            titles_found = data[1] if len(data) > 1 else []
            urls_found   = data[3] if len(data) > 3 else []

            for wp_title, wp_url in zip(titles_found, urls_found):
                time.sleep(0.5)
                text = wp_fetch_extract(wp_title)
                ok, reason = validate(text, title, author)
                if ok:
                    intro = extract_intro(text)
                    if intro:
                        return intro[:600], wp_url
                # Sinon on essaie le résultat suivant

        except requests.RequestException as e:
            log.warning(f'  Erreur API: {e}')
            time.sleep(5)
            continue

    return None, None

# ── Cibles ────────────────────────────────────────────────────────────────────
cur.execute("""
    SELECT title_id, title, author, year, "type" as work_type
    FROM works
    WHERE (dp_eu=1 OR dp_us=1)
      AND has_french_vf=0
      AND synopsis IS NULL
      AND (wp_searched IS NULL OR wp_searched=0)
    ORDER BY
        CASE WHEN award_count > 0 THEN 0 ELSE 1 END,
        COALESCE(annualviews,0)/1000.0 + COALESCE(nb_langues_vf,0)*5 DESC,
        annualviews DESC NULLS LAST
""")
targets = cur.fetchall()
total = len(targets)
log.info(f'Cibles : {total} œuvres sans synopsis')

# ── Run ───────────────────────────────────────────────────────────────────────
found = not_found = errors = 0

for i, row in enumerate(targets):
    tid        = row['title_id']
    title      = row['title']
    author     = row['author']
    work_type  = row['work_type']

    if i > 0 and i % 100 == 0:
        pct = i / total * 100
        log.info(f'--- Progression : {i}/{total} ({pct:.1f}%) | trouvés={found} non_trouvés={not_found} erreurs={errors} ---')

    if i > 0 and i % COMMIT_N == 0:
        conn.commit()
        log.info(f'💾 Checkpoint {i}')

    try:
        synopsis, wp_url = wp_search(title, author, work_type)
        time.sleep(WAIT)

        if synopsis:
            cur.execute("""
                UPDATE works SET
                    synopsis=?,
                    synopsis_source='wikipedia_search',
                    wikipedia_url=COALESCE(wikipedia_url, ?),
                    wp_searched=1
                WHERE title_id=?
            """, (synopsis, wp_url, tid))
            found += 1
            log.info(f'[{i+1}/{total}] ✅ {author} — {title}')
        else:
            cur.execute("UPDATE works SET wp_searched=1 WHERE title_id=?", [tid])
            not_found += 1
            if i % 50 == 0:
                log.info(f'[{i+1}/{total}] — {author} — {title}')

    except Exception as e:
        log.warning(f'[{i+1}/{total}] Erreur {tid} ({title}): {e}')
        cur.execute("UPDATE works SET wp_searched=1 WHERE title_id=?", [tid])
        errors += 1

conn.commit()

# ── Stats finales ─────────────────────────────────────────────────────────────
total_synopsis = conn.execute("SELECT COUNT(*) FROM works WHERE synopsis IS NOT NULL").fetchone()[0]
log.info(f'')
log.info(f'=== STATS FINALES ===')
log.info(f'  Traités      : {total}')
log.info(f'  Trouvés      : {found}')
log.info(f'  Non trouvés  : {not_found}')
log.info(f'  Erreurs      : {errors}')
log.info(f'  Taux succès  : {found/total*100:.1f}%')
log.info(f'  Total synopsis en base : {total_synopsis}')
log.info(f'✅ Terminé à {datetime.now().strftime("%H:%M:%S")}')
