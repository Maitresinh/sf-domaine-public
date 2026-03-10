"""
13_reviews.py
Enrichissement critiques : Goodreads (rating + textes) + The Guardian
Puis synthèse Ollama des critiques scraped.

Sources :
  1. Goodreads scraping → gr_rating, gr_votes, gr_toread, gr_reviews_text (JSON)
  2. The Guardian API → guardian_url, guardian_title, guardian_date, guardian_snippet
  3. Ollama gemma3 → gr_summary (synthèse des critiques GR, si ≥2 critiques)

Lancer :
  docker exec -d sf-dp-tools bash -c "python3 /app/13_reviews.py >> /app/data/reviews.log 2>&1 && echo DONE >> /app/data/reviews.log"
  tail -f /mnt/user/sf-dp/data/reviews.log
"""
import fcntl, sys
_lf = open("/app/data/13.lock", "w")
try:
    fcntl.flock(_lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
except IOError:
    print("Instance déjà en cours. Abandon.")
    sys.exit(0)

import sqlite3, requests, time, logging, json, re
from datetime import datetime

DB           = '/app/data/sf_dp.sqlite'
LOG_FILE     = '/app/data/reviews.log'
GUARDIAN_KEY = '8146d1a6-eaaa-4feb-88de-d31af3ae6b6f'
OLLAMA_URL   = 'http://ollama:11434/api/generate'
HEADERS_BR   = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}
HEADERS_API  = {'User-Agent': 'sf-domaine-public/1.0 (public-domain-research)'}

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()])
log = logging.getLogger()

conn = sqlite3.connect(DB, timeout=30)
conn.row_factory = sqlite3.Row
cur  = conn.cursor()

# ── Schema migrations ──────────────────────────────────────────────────────────
for col, defn in [
    ('gr_rating',       'REAL'),
    ('gr_votes',        'INTEGER'),
    ('gr_toread',       'INTEGER'),
    ('gr_reviews_text', 'TEXT'),   # JSON array de strings
    ('gr_summary',      'TEXT'),   # synthèse Ollama
    ('gr_searched',     'INTEGER DEFAULT 0'),
    ('guardian_url',    'TEXT'),
    ('guardian_title',  'TEXT'),
    ('guardian_date',   'TEXT'),
    ('guardian_snippet','TEXT'),
    ('guardian_searched','INTEGER DEFAULT 0'),
]:
    try:
        cur.execute(f'ALTER TABLE works ADD COLUMN {col} {defn}')
        log.info(f'Colonne {col} ajoutée')
    except Exception:
        pass
conn.commit()

def ckpt(n, every=100):
    if n % every == 0:
        conn.commit()
        log.info(f'  💾 checkpoint {n}')

# ═══════════════════════════════════════════════════════════════════════════════
# ÉTAPE 1 — Goodreads scraping
# ═══════════════════════════════════════════════════════════════════════════════
log.info('\n=== ÉTAPE 1 : Goodreads ===')

cur.execute("""
    SELECT title_id, title, author, goodreads_id
    FROM works
    WHERE (dp_eu=1 OR dp_us=1) AND has_french_vf=0
    AND goodreads_id IS NOT NULL AND goodreads_id != ''
    AND (gr_searched IS NULL OR gr_searched = 0)
    ORDER BY annualviews DESC NULLS LAST, award_count DESC
""")
gr_targets = list(cur.fetchall())
log.info(f'  {len(gr_targets)} cibles Goodreads')

gr_ok = gr_err = 0
for i, row in enumerate(gr_targets):
    tid, gid = row['title_id'], str(row['goodreads_id']).strip()
    try:
        url = f'https://www.goodreads.com/book/show/{gid}'
        r = requests.get(url, headers=HEADERS_BR, timeout=15)
        if r.status_code == 429:
            log.warning('  GR rate limit — pause 60s')
            time.sleep(60)
            r = requests.get(url, headers=HEADERS_BR, timeout=15)
        if r.status_code != 200:
            cur.execute('UPDATE works SET gr_searched=1 WHERE title_id=?', (tid,))
            ckpt(i+1); time.sleep(2); continue

        html = r.text

        # Note moyenne
        rating = None
        m = re.search(r'"ratingValue"\s*:\s*"?([\d.]+)"?', html)
        if not m:
            m = re.search(r'class="RatingStatistics__rating[^"]*"[^>]*>([\d.]+)<', html)
        if m:
            try: rating = float(m.group(1))
            except: pass

        # Nb votes
        votes = None
        m = re.search(r'"ratingCount"\s*:\s*"?(\d+)"?', html)
        if not m:
            m = re.search(r'([\d,]+)\s*rating', html)
        if m:
            try: votes = int(m.group(1).replace(',', ''))
            except: pass

        # To-read
        toread = None
        m = re.search(r'([\d,]+)\s*people want to read', html)
        if m:
            try: toread = int(m.group(1).replace(',', ''))
            except: pass

        # Extraits de critiques (Community Reviews)
        reviews = []
        for m in re.finditer(
            r'<span[^>]*class="[^"]*Formatted[^"]*"[^>]*>(.*?)</span>',
            html, re.DOTALL
        ):
            text = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            text = re.sub(r'\s+', ' ', text)
            if len(text) > 100 and len(text) < 2000:
                reviews.append(text)
            if len(reviews) >= 5:
                break

        reviews_json = json.dumps(reviews, ensure_ascii=False) if reviews else None

        cur.execute("""
            UPDATE works SET
                gr_rating=?, gr_votes=?, gr_toread=?,
                gr_reviews_text=?, gr_searched=1
            WHERE title_id=?
        """, (rating, votes, toread, reviews_json, tid))

        if rating: gr_ok += 1
        ckpt(i+1)
        time.sleep(2.5)  # respectueux

    except Exception as e:
        gr_err += 1
        cur.execute('UPDATE works SET gr_searched=1 WHERE title_id=?', (tid,))
        if gr_err <= 5:
            log.warning(f'  GR err [{tid}]: {e}')
        time.sleep(3)

conn.commit()
log.info(f'  ✅ Goodreads : {gr_ok} notes, {gr_err} erreurs')

# ═══════════════════════════════════════════════════════════════════════════════
# ÉTAPE 2 — The Guardian
# ═══════════════════════════════════════════════════════════════════════════════
log.info('\n=== ÉTAPE 2 : The Guardian ===')

cur.execute("""
    SELECT title_id, title, author
    FROM works
    WHERE (dp_eu=1 OR dp_us=1) AND has_french_vf=0
    AND (guardian_searched IS NULL OR guardian_searched = 0)
    AND (award_count > 0 OR annualviews > 500 OR nb_langues_vf >= 3)
    ORDER BY annualviews DESC NULLS LAST, award_count DESC
    LIMIT 3000
""")
gd_targets = list(cur.fetchall())
log.info(f'  {len(gd_targets)} cibles Guardian')

gd_ok = gd_err = 0
for i, row in enumerate(gd_targets):
    tid = row['title_id']
    lastname = str(row['author']).split()[-1] if row['author'] else ''
    q = f"{row['title']} {lastname}"
    try:
        r = requests.get(
            'https://content.guardianapis.com/search',
            headers=HEADERS_API, timeout=10,
            params={
                'q': q,
                'section': 'books',
                'tag': 'books/books',
                'show-fields': 'trailText,headline,byline',
                'page-size': 3,
                'api-key': GUARDIAN_KEY,
            }
        )
        results = r.json().get('response', {}).get('results', [])

        matched = None
        title_low = str(row['title']).lower()
        for res in results:
            headline = res.get('webTitle', '').lower()
            if title_low[:12] in headline or lastname.lower() in headline:
                matched = res
                break

        if matched:
            fields = matched.get('fields', {})
            snippet = re.sub(r'<[^>]+>', '', fields.get('trailText', ''))
            cur.execute("""
                UPDATE works SET
                    guardian_url=?, guardian_title=?,
                    guardian_date=?, guardian_snippet=?,
                    guardian_searched=1
                WHERE title_id=?
            """, (
                matched.get('webUrl'),
                matched.get('webTitle'),
                matched.get('webPublicationDate', '')[:10],
                snippet[:500] or None,
                tid
            ))
            gd_ok += 1
        else:
            cur.execute('UPDATE works SET guardian_searched=1 WHERE title_id=?', (tid,))

        ckpt(i+1)
        time.sleep(0.25)

    except Exception as e:
        gd_err += 1
        cur.execute('UPDATE works SET guardian_searched=1 WHERE title_id=?', (tid,))
        if gd_err <= 5:
            log.warning(f'  Guardian err [{tid}]: {e}')

conn.commit()
log.info(f'  ✅ Guardian : {gd_ok} articles trouvés, {gd_err} erreurs')

# ═══════════════════════════════════════════════════════════════════════════════
# ÉTAPE 3 — Synthèse Ollama des critiques Goodreads
# ═══════════════════════════════════════════════════════════════════════════════
log.info('\n=== ÉTAPE 3 : Synthèse Ollama ===')

cur.execute("""
    SELECT title_id, title, author, gr_reviews_text
    FROM works
    WHERE gr_reviews_text IS NOT NULL AND gr_reviews_text != '[]'
    AND (gr_summary IS NULL OR gr_summary = '')
    ORDER BY annualviews DESC NULLS LAST
    LIMIT 500
""")
ol_targets = list(cur.fetchall())
log.info(f'  {len(ol_targets)} cibles pour synthèse')

ol_ok = ol_err = 0
for i, row in enumerate(ol_targets):
    tid = row['title_id']
    try:
        reviews = json.loads(row['gr_reviews_text'])
        if len(reviews) < 2:
            continue

        reviews_block = '\n\n'.join(f'— {r[:400]}' for r in reviews[:5])
        prompt = (
            f"Book: \"{row['title']}\" by {row['author']}\n\n"
            f"Reader reviews:\n{reviews_block}\n\n"
            "Write a neutral 3-sentence summary of these reader opinions "
            "in English. Focus on what readers praise or criticize. "
            "Do not invent anything not in the reviews."
        )

        r = requests.post(OLLAMA_URL, json={
            'model': 'gemma3:latest',
            'prompt': prompt,
            'stream': False,
            'options': {'temperature': 0.3, 'num_predict': 150}
        }, timeout=60)

        summary = r.json().get('response', '').strip()
        if summary and len(summary) > 50:
            cur.execute('UPDATE works SET gr_summary=? WHERE title_id=?', (summary, tid))
            ol_ok += 1

        ckpt(i+1, every=50)
        time.sleep(0.5)

    except Exception as e:
        ol_err += 1
        if ol_err <= 5:
            log.warning(f'  Ollama err [{tid}]: {e}')

conn.commit()
log.info(f'  ✅ Ollama synthèse : {ol_ok} summaries, {ol_err} erreurs')

# ═══════════════════════════════════════════════════════════════════════════════
# STATS FINALES
# ═══════════════════════════════════════════════════════════════════════════════
log.info('\n=== STATS FINALES ===')
for label, sql in [
    ('GR rating récupéré',    'SELECT COUNT(*) FROM works WHERE gr_rating IS NOT NULL'),
    ('GR reviews texte',      "SELECT COUNT(*) FROM works WHERE gr_reviews_text IS NOT NULL AND gr_reviews_text != '[]'"),
    ('GR summary Ollama',     "SELECT COUNT(*) FROM works WHERE gr_summary IS NOT NULL AND gr_summary != ''"),
    ('Guardian articles',     'SELECT COUNT(*) FROM works WHERE guardian_url IS NOT NULL'),
    ('GR note moyenne DP/sVF','SELECT ROUND(AVG(gr_rating),2) FROM works WHERE (dp_eu=1 OR dp_us=1) AND has_french_vf=0 AND gr_rating IS NOT NULL'),
]:
    cur.execute(sql)
    log.info(f'  {label:40s}: {cur.fetchone()[0]}')

log.info(f'\n✅ Terminé à {datetime.now().strftime("%H:%M:%S")}')
conn.close()
