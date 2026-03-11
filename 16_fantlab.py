"""
16_fantlab.py
Enrichissement FantLab : rating, votes, url pour les œuvres DP sans VF.
Cibles : dp_eu=1 AND dp_us=1 AND has_french_vf=0 AND fantlab_rating IS NULL
API : https://api.fantlab.ru/search/works?q=TITLE+AUTHOR
Prudent : timeout SQLite 60s, commit toutes les 50 lignes, pause 1.5s/req.
"""
import fcntl, sys
_lf = open("/app/data/16.lock", "w")
try:
    fcntl.flock(_lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
except IOError:
    print("Instance deja en cours. Abandon."); sys.exit(0)

import sqlite3, requests, time, logging, re, unicodedata, json
from datetime import datetime

DB       = '/app/data/sf_dp.sqlite'
LOG_FILE = '/app/data/16_fantlab.log'
HEADERS  = {
    'User-Agent': 'sf-domaine-public/1.0 (public-domain-research)',
    'Accept': 'application/json',
}
PAUSE    = 1.5   # secondes entre requêtes
COMMIT_N = 50    # commit toutes les N lignes

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()])
log = logging.getLogger()
log.info('=== 16_fantlab.py ===')

conn = sqlite3.connect(DB, timeout=60)
conn.row_factory = sqlite3.Row
sc = conn.cursor()

# Colonnes FantLab
for col, defn in [
    ('fantlab_id',      'INTEGER'),
    ('fantlab_rating',  'REAL'),
    ('fantlab_votes',   'INTEGER'),
    ('fantlab_url',     'TEXT'),
]:
    try:
        sc.execute(f'ALTER TABLE works ADD COLUMN {col} {defn}')
    except Exception:
        pass
conn.commit()

def norm(s):
    s = str(s).lower().strip()
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    return re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', ' ', s)).strip()

def similarity(a, b):
    a, b = norm(a), norm(b)
    if a == b: return 1.0
    wa, wb = set(a.split()), set(b.split())
    if not wa or not wb: return 0.0
    return len(wa & wb) / len(wa | wb)

def fantlab_search(title, author):
    """Cherche une œuvre sur FantLab, retourne (id, rating, votes) ou None."""
    q = f"{title} {author}"
    try:
        r = requests.get(
            'https://api.fantlab.ru/search/works',
            params={'q': q, 'page': 1},
            headers=HEADERS, timeout=12)
        if r.status_code != 200:
            return None
        data = r.json()
        items = data if isinstance(data, list) else data.get('works', data.get('items', []))
        if not items:
            return None
        # Cherche le meilleur match titre+auteur
        best = None
        best_score = 0.4  # seuil minimum
        for item in items[:5]:
            t_fl = item.get('work_name_orig') or item.get('work_name', '')
            a_fl = item.get('author_name', '')
            score = (similarity(title, t_fl) * 0.7 + similarity(author, a_fl) * 0.3)
            if score > best_score:
                best_score = score
                best = item
        if not best:
            return None
        wid     = best.get('work_id')
        rating  = best.get('rating', {})
        if isinstance(rating, dict):
            r_val   = rating.get('rating') or rating.get('avg')
            r_votes = rating.get('voters') or rating.get('votes', 0)
        else:
            r_val, r_votes = rating, 0
        if not r_val:
            return None
        return {
            'id':     wid,
            'rating': round(float(r_val), 2),
            'votes':  int(r_votes or 0),
            'url':    f'https://fantlab.ru/work{wid}' if wid else None,
        }
    except Exception as e:
        log.debug(f'  FantLab err: {e}')
        return None

# Cibles : DP EU+US sans VF, pas encore enrichi FantLab
sc.execute("""
    SELECT title_id, title, author, year, "type"
    FROM works
    WHERE dp_eu=1 AND dp_us=1 AND has_french_vf=0
      AND fantlab_rating IS NULL
      AND "type" IN ('novel','collection','anthology','novelette','novella','short story','shortfiction')
    ORDER BY award_count DESC NULLS LAST, annualviews DESC NULLS LAST
""")
targets = list(sc.fetchall())
log.info(f'  {len(targets)} cibles à enrichir')

n_found = n_miss = n_err = 0
for i, row in enumerate(targets, 1):
    tid    = row['title_id']
    title  = row['title']  or ''
    author = row['author'] or ''

    result = fantlab_search(title, author)
    time.sleep(PAUSE)

    if result:
        sc.execute("""
            UPDATE works SET
                fantlab_id=?, fantlab_rating=?, fantlab_votes=?, fantlab_url=?
            WHERE title_id=?
        """, (result['id'], result['rating'], result['votes'], result['url'], tid))
        n_found += 1
        if n_found <= 20 or n_found % 100 == 0:
            log.info(f'  ✅ [{row["year"]}] {author} — {title} → {result["rating"]} ({result["votes"]} votes)')
    else:
        n_miss += 1

    if i % COMMIT_N == 0:
        conn.commit()
        log.info(f'  💾 Checkpoint {i}/{len(targets)} — trouvés: {n_found}, manqués: {n_miss}')

conn.commit()
log.info(f'\n=== RÉSULTAT ===')
log.info(f'  Trouvés  : {n_found}')
log.info(f'  Manqués  : {n_miss}')
log.info(f'  Erreurs  : {n_err}')
log.info(f'  fantlab_rating renseigné : {sc.execute("SELECT COUNT(*) FROM works WHERE fantlab_rating IS NOT NULL").fetchone()[0]}')
log.info(f'\n✅ Terminé à {datetime.now().strftime("%H:%M:%S")}')
conn.close()
_lf.close()
