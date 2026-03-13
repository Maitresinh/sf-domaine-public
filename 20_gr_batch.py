
"""
20_gr_batch.py
Batch nocturne Goodreads — scraping progressif priorisé.

Priorités :
  1. DP EU ou US + sans VF + primés (award_count > 0)
  2. DP EU ou US + sans VF + score ≥ MIN_SCORE
     score = annualviews/1000 + nb_langues_vf*5 + award_score

Volume : LIMIT livres par run (défaut 150 ≈ 1h15)
Backoff : pause exponentielle sur 429/403 (30s → 60s → 120s → abandon session)

Lancer la nuit :
  docker exec -d sf-dp-tools python3 /app/20_gr_batch.py
  # Suivre :
  docker exec sf-dp-tools tail -f /app/data/20_gr_batch.log
"""
import fcntl, sys
_lf = open("/app/data/20.lock", "w")
try:
    fcntl.flock(_lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
except IOError:
    print("Instance déjà en cours. Abandon.")
    sys.exit(0)

import sqlite3, requests, time, logging, re, json
from bs4 import BeautifulSoup
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
DB        = '/app/data/sf_dp.sqlite'
LOG_FILE  = '/app/data/20_gr_batch.log'
LIMIT     = 150      # livres par run
WAIT      = 18       # secondes entre requêtes (poli)
MIN_SCORE = 10       # score minimum pour priorité 2
           # annualviews/1000 + nb_langues_vf*5 + award_score

HEADERS_LIST = [
    {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36'},
    {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/605.1.15 Version/17.2 Safari/605.1.15'},
    {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0'},
]
_ua = [0]
def hdrs():
    h = HEADERS_LIST[_ua[0] % len(HEADERS_LIST)]
    _ua[0] += 1
    return h

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
log.info(f'=== 20_gr_batch.py — {datetime.now().strftime("%Y-%m-%d %H:%M")} ===')

# ── DB ────────────────────────────────────────────────────────────────────────
conn = sqlite3.connect(DB, timeout=60)
conn.row_factory = sqlite3.Row
cur  = conn.cursor()

for col, defn in [
    ('gr_rating',       'REAL'),
    ('gr_votes',        'INTEGER'),
    ('gr_toread',       'INTEGER'),
    ('gr_reviews_text', 'TEXT'),
    ('gr_summary',      'TEXT'),
    ('gr_searched',     'INTEGER DEFAULT 0'),
    ('goodreads_id',    'TEXT'),
]:
    try:
        cur.execute(f'ALTER TABLE works ADD COLUMN {col} {defn}')
    except Exception:
        pass
conn.commit()

# ── Cibles ────────────────────────────────────────────────────────────────────
# Priorité 1 : DP EU ou US + sans VF + primés
cur.execute("""
    SELECT title_id, title, author, year, award_count, annualviews, nb_langues_vf, award_score
    FROM works
    WHERE (dp_eu=1 OR dp_us=1)
      AND has_french_vf=0
      AND award_count > 0
      AND (gr_searched IS NULL OR gr_searched=0)
    ORDER BY award_count DESC, award_score DESC NULLS LAST, annualviews DESC NULLS LAST
""")
p1 = cur.fetchall()

# Priorité 2 : DP EU ou US + sans VF + score ≥ MIN_SCORE
cur.execute(f"""
    SELECT title_id, title, author, year, award_count, annualviews, nb_langues_vf, award_score
    FROM works
    WHERE (dp_eu=1 OR dp_us=1)
      AND has_french_vf=0
      AND (award_count IS NULL OR award_count=0)
      AND (gr_searched IS NULL OR gr_searched=0)
      AND (
        COALESCE(annualviews,0)/1000.0
        + COALESCE(nb_langues_vf,0)*5
        + COALESCE(award_score,0)
      ) >= {MIN_SCORE}
    ORDER BY
        COALESCE(annualviews,0)/1000.0
        + COALESCE(nb_langues_vf,0)*5
        + COALESCE(award_score,0) DESC
""")
p2 = cur.fetchall()

targets = (list(p1) + list(p2))[:LIMIT]
log.info(f'Cibles : {len(p1)} P1 + {len(p2)} P2 → run limité à {LIMIT}')
log.info(f'  Sélectionnés ce run : {len(targets)} ({min(len(p1),LIMIT)} P1, {max(0,len(targets)-len(p1))} P2)')

# ── Scraping ──────────────────────────────────────────────────────────────────
def search_gr(title, author):
    q   = f'{title} {author.split()[-1] if author else ""}'
    url = 'https://www.goodreads.com/search?q=' + requests.utils.quote(q)
    r   = requests.get(url, headers=hdrs(), timeout=15)
    if r.status_code == 429: return None, 429
    if r.status_code != 200: return None, r.status_code
    soup = BeautifulSoup(r.text, 'html.parser')
    link = soup.select_one('a.bookTitle')
    if link:
        href = link['href'].split('?')[0]
        # extraire goodreads_id depuis /book/show/12345
        m = re.search(r'/show/(\d+)', href)
        gid = m.group(1) if m else None
        return 'https://www.goodreads.com' + href, 200, gid
    return None, 404, None

def scrape_gr(url):
    r = requests.get(url, headers=hdrs(), timeout=15)
    if r.status_code == 429: return None, 429
    if r.status_code != 200: return None, r.status_code
    soup   = BeautifulSoup(r.text, 'html.parser')
    result = {}
    el = soup.select_one('div.RatingStatistics__rating')
    if el:
        try: result['gr_rating'] = float(el.text.strip())
        except: pass
    el = soup.select_one('span[data-testid="ratingsCount"]')
    if el:
        v = re.sub(r'[^\d]', '', el.text)
        if v: result['gr_votes'] = int(v)
    el = soup.select_one('span[data-testid="toReadCount"]')
    if el:
        v = re.sub(r'[^\d]', '', el.text)
        if v: result['gr_toread'] = int(v)
    el = soup.select_one('div.BookPageMetadataSection__description span.Formatted')
    if el: result['gr_summary'] = el.text.strip()[:600]
    revs = [rv.text.strip()[:300] for rv in soup.select('section.ReviewText span.Formatted')[:3] if len(rv.text.strip()) > 50]
    if revs: result['gr_reviews_text'] = json.dumps(revs, ensure_ascii=False)
    return result or None, 200

def backoff(attempt):
    """Pause exponentielle : 30, 60, 120s."""
    pause = min(30 * (2 ** attempt), 120)
    log.warning(f'  Backoff {pause}s (tentative {attempt+1})')
    time.sleep(pause)

# ── Run ───────────────────────────────────────────────────────────────────────
found = skipped = blocked = 0
block_streak = 0  # blocages consécutifs

for i, row in enumerate(targets):
    tid, title, author = row['title_id'], row['title'], row['author']
    log.info(f'[{i+1}/{len(targets)}] {author} — {title}')

    # Abandon si trop de blocages consécutifs
    if block_streak >= 3:
        log.error('3 blocages consécutifs — abandon du run pour ce soir')
        break

    try:
        # 1. Recherche
        res = search_gr(title, author)
        if len(res) == 2:  # erreur sans gid
            url, status = res
            gid = None
        else:
            url, status, gid = res

        time.sleep(WAIT)

        if status == 429:
            backoff(block_streak)
            block_streak += 1
            blocked += 1
            cur.execute('UPDATE works SET gr_searched=1 WHERE title_id=?', [tid])
            conn.commit()
            continue

        if not url:
            log.info(f'  Non trouvé (HTTP {status})')
            skipped += 1
            cur.execute('UPDATE works SET gr_searched=1 WHERE title_id=?', [tid])
            conn.commit()
            block_streak = 0
            continue

        log.info(f'  → {url}')

        # 2. Scrape page livre
        result = scrape_gr(url)
        if isinstance(result, tuple):
            data, status2 = result
        else:
            data, status2 = result, 200

        time.sleep(WAIT)

        if status2 == 429:
            backoff(block_streak)
            block_streak += 1
            blocked += 1
            cur.execute('UPDATE works SET gr_searched=1 WHERE title_id=?', [tid])
            conn.commit()
            continue

        block_streak = 0

        if data:
            data['gr_searched'] = 1
            if gid: data['goodreads_id'] = gid
            sets = ', '.join(f'{k}=?' for k in data)
            vals = list(data.values()) + [tid]
            cur.execute(f'UPDATE works SET {sets} WHERE title_id=?', vals)
            found += 1
            log.info(f'  ✅ rating={data.get("gr_rating","?")} votes={data.get("gr_votes","?")} reviews={len(json.loads(data["gr_reviews_text"])) if "gr_reviews_text" in data else 0}')
        else:
            cur.execute('UPDATE works SET gr_searched=1 WHERE title_id=?', [tid])
            skipped += 1

        conn.commit()

    except Exception as e:
        log.warning(f'  Erreur {tid}: {e}')
        if '429' in str(e) or '403' in str(e):
            backoff(block_streak)
            block_streak += 1
            blocked += 1
        cur.execute('UPDATE works SET gr_searched=1 WHERE title_id=?', [tid])
        conn.commit()

# ── Stats finales ─────────────────────────────────────────────────────────────
total_rated = conn.execute("SELECT COUNT(*) FROM works WHERE gr_rating IS NOT NULL").fetchone()[0]
remaining_p1 = conn.execute("""
    SELECT COUNT(*) FROM works
    WHERE (dp_eu=1 OR dp_us=1) AND has_french_vf=0 AND award_count>0
    AND (gr_searched IS NULL OR gr_searched=0)
""").fetchone()[0]
remaining_p2 = conn.execute(f"""
    SELECT COUNT(*) FROM works
    WHERE (dp_eu=1 OR dp_us=1) AND has_french_vf=0
    AND (award_count IS NULL OR award_count=0)
    AND (gr_searched IS NULL OR gr_searched=0)
    AND (COALESCE(annualviews,0)/1000.0 + COALESCE(nb_langues_vf,0)*5 + COALESCE(award_score,0)) >= {MIN_SCORE}
""").fetchone()[0]

log.info(f'')
log.info(f'=== STATS RUN ===')
log.info(f'  Trouvés     : {found}')
log.info(f'  Non trouvés : {skipped}')
log.info(f'  Bloqués     : {blocked}')
log.info(f'  Total DB avec rating : {total_rated}')
log.info(f'  Restants P1 : {remaining_p1}')
log.info(f'  Restants P2 : {remaining_p2}')
days_left = (remaining_p1 + remaining_p2) / max(found, 1) if found > 0 else 0
log.info(f'  Estimation fin P1+P2 : ~{days_left:.0f} nuits à ce rythme')
log.info(f'✅ Terminé à {datetime.now().strftime("%H:%M:%S")}')
