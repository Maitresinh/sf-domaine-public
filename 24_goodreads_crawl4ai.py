"""
24_goodreads_crawl4ai.py
Enrichissement Goodreads via Crawl4AI + Playwright.

Priorites :
  P1 : DP EU+US, sans VF, primees (award_count > 0)
  P2 : DP EU+US, sans VF, traduit >= 3 langues
  P3 : DP EU+US, sans VF, populaires (CAST(annualviews AS INTEGER) > 500)
  P4 : DP EU+US, VF ancienne (<= 1995)
"""
import fcntl, sys
_lf = open("/app/data/24.lock", "w")
try:
    fcntl.flock(_lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
except IOError:
    print("Instance deja en cours. Abandon."); sys.exit(0)

import asyncio, sqlite3, json, re, logging, random
from datetime import datetime
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode

DB       = '/app/data/sf_dp.sqlite'
LOG_FILE = '/app/data/24_goodreads.log'
COMMIT_N = 20
WAIT_MIN = 8
WAIT_MAX = 15
MAX_RETRIES = 2

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()])
log = logging.getLogger()
log.info('=== 24_goodreads_crawl4ai.py ===')

conn = sqlite3.connect(DB, timeout=120)
conn.row_factory = sqlite3.Row
sc = conn.cursor()

for col, defn in [('cover_url','TEXT'), ('gr_summary','TEXT')]:
    try:
        sc.execute(f'ALTER TABLE works ADD COLUMN {col} {defn}')
        conn.commit()
        log.info(f'  Colonne {col} creee')
    except Exception:
        pass

sc.execute("""
    SELECT title_id, title, author, year, goodreads_id,
           award_count, nb_langues_vf, annualviews,
           has_french_vf, last_vf_year, death_year,
           dp_eu, dp_us
    FROM works
    WHERE (gr_summary IS NULL OR gr_summary = '')
      AND goodreads_id IS NOT NULL
      AND (
          (dp_eu=1 AND dp_us=1)
          OR (death_year BETWEEN 1956 AND 1971
              AND (CAST(annualviews AS INTEGER)/1000
                   + COALESCE(nb_langues_vf,0)*5
                   + COALESCE(award_score,0)) >= 5)
      )
    ORDER BY
        CASE
            WHEN dp_eu=1 AND dp_us=1 AND has_french_vf=0 AND award_count > 0 THEN 1
            WHEN dp_eu=1 AND dp_us=1 AND has_french_vf=0 AND nb_langues_vf >= 3 THEN 2
            WHEN dp_eu=1 AND dp_us=1 AND has_french_vf=0
                 AND CAST(annualviews AS INTEGER) > 500 THEN 3
            WHEN dp_eu=1 AND dp_us=1 AND has_french_vf=0 THEN 4
            WHEN dp_eu=1 AND dp_us=1
                 AND CAST(last_vf_year AS INTEGER) <= 1975 THEN 5
            WHEN dp_eu=1 AND dp_us=1
                 AND CAST(last_vf_year AS INTEGER) <= 1995 THEN 6
            WHEN dp_eu=1 AND dp_us=1 THEN 7
            WHEN death_year BETWEEN 1956 AND 1971 THEN 8
            ELSE 9
        END,
        award_count DESC,
        annualviews DESC NULLS LAST
""")
targets = list(sc.fetchall())

p1 = sum(1 for r in targets if r['has_french_vf']==0 and (r['award_count'] or 0)>0)
p2 = sum(1 for r in targets if r['has_french_vf']==0 and (r['nb_langues_vf'] or 0)>=3)
p3 = sum(1 for r in targets if r['has_french_vf']==0 and int(r['annualviews'] or 0)>500)
p4 = sum(1 for r in targets if r['has_french_vf']==1)
log.info(f'  Cibles : {len(targets)} total')
log.info(f'    P1 sans VF + primees    : {p1}')
log.info(f'    P2 sans VF + 3 langues  : {p2}')
log.info(f'    P3 sans VF + populaires : {p3}')
log.info(f'    P4 VF ancienne (<1995)  : {p4}')

RUN_CONFIG = CrawlerRunConfig(
    cache_mode=CacheMode.BYPASS,
    wait_for="css:.BookPage__mainContent",
    page_timeout=25000,
    delay_before_return_html=2.5,
)

def extract_rating(text):
    m = re.search(r'^\s*(\d\.\d{2})\s*$', text, re.MULTILINE)
    if m: return float(m.group(1))
    m = re.search(r'\[(\d\.\d{2})\s+[\d,]+\s+ratings', text)
    if m: return float(m.group(1))
    return None

def extract_votes(text):
    m = re.search(r'([\d,]+)\s*ratings', text, re.IGNORECASE)
    if m: return int(m.group(1).replace(',',''))
    return None

def extract_cover(html):
    m = re.search(r'https://[^"\']+compressed\.photo\.goodreads[^"\']+\.jpg', html or '')
    return m.group(0) if m else None

def extract_description(text):
    lines = text.split('\n')
    desc_lines = []
    for line in lines:
        line = line.strip()
        if not line: continue
        if line.startswith('[') or line.startswith('!') or line.startswith('#'): continue
        if line.startswith('*'): continue
        if 'goodreads.com' in line.lower(): continue
        if re.search(r'(kindle|paperback|hardcover|buy on|want to read|nav_brws)', line, re.I): continue
        if re.search(r'(displaying \d+|ratings & reviews|community reviews)', line, re.I): break
        if len(line) > 80:
            desc_lines.append(line)
        if len(desc_lines) >= 5:
            break
    return ' '.join(desc_lines)[:2000] if desc_lines else None

def extract_reviews(text):
    reviews = []
    lines = text.split('\n')
    in_reviews = False
    current = []
    for line in lines:
        line = line.strip()
        if not line: continue
        if re.search(r'displaying \d+ - \d+ of \d+ reviews', line, re.IGNORECASE):
            in_reviews = True
            continue
        if not in_reviews:
            continue
        if line.startswith('[') or line.startswith('!') or len(line) < 25:
            continue
        if current and line[0].isupper() and len(' '.join(current)) > 120:
            t = ' '.join(current).strip()
            if len(t) > 80: reviews.append(t[:400])
            current = [line]
        else:
            current.append(line)
        if len(reviews) >= 5: break
    if current:
        t = ' '.join(current).strip()
        if len(t) > 80: reviews.append(t[:400])
    return reviews[:5]

async def scrape(crawler, gid, title, author):
    url = f"https://www.goodreads.com/book/show/{gid}"
    for attempt in range(MAX_RETRIES):
        try:
            result = await crawler.arun(url=url, config=RUN_CONFIG)
            if result.success and len(result.markdown or '') > 1000:
                return result
            log.warning(f'  Contenu court ({len(result.markdown or "")} chars)')
        except Exception as e:
            log.warning(f'  Tentative {attempt+1}: {e}')
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(30)
    return None

async def main():
    n_done = n_ok = n_fail = 0

    async with AsyncWebCrawler(verbose=False) as crawler:
        log.info(f'  Debut : {len(targets)} cibles')

        for row in targets:
            n_done += 1
            tid    = row['title_id']
            title  = row['title']
            author = row['author']
            year   = row['year']
            gid    = row['goodreads_id']
            vf_tag = f'(VF {row["last_vf_year"]})' if row['has_french_vf']==1 else '(sans VF)'

            result = await scrape(crawler, gid, title, author)

            if not result:
                n_fail += 1
                log.warning(f'  [{n_done}] ECHEC {vf_tag}: {author} — {title}')
                sc.execute("UPDATE works SET gr_searched=1 WHERE title_id=?", (tid,))
            else:
                md   = result.markdown or ''
                html = result.html or ''

                rating  = extract_rating(md)
                votes   = extract_votes(md)
                desc    = extract_description(md)
                reviews = extract_reviews(md)
                cover   = extract_cover(html)

                sc.execute("""UPDATE works SET
                    gr_rating=?, gr_votes=?, gr_summary=?,
                    gr_reviews_text=?, cover_url=?, gr_searched=1
                    WHERE title_id=?""",
                    (rating, votes, desc,
                     json.dumps(reviews, ensure_ascii=False) if reviews else None,
                     cover, tid))
                n_ok += 1
                log.info(f'  [{n_done}] OK {vf_tag}: {author} — {title} ({year}) '
                         f'| {rating} ({votes} votes) '
                         f'desc={len(desc or "")}c rev={len(reviews)}')

            if n_done % COMMIT_N == 0:
                conn.commit()
                log.info(f'  CHECKPOINT {n_done}/{len(targets)} OK:{n_ok} FAIL:{n_fail}')

            if n_done < len(targets):
                await asyncio.sleep(random.uniform(WAIT_MIN, WAIT_MAX))

    conn.commit()
    log.info('=== STATS FINALES ===')
    for label, sql in [
        ('gr_summary rensegne',  "SELECT COUNT(*) FROM works WHERE gr_summary IS NOT NULL AND gr_summary!=''"),
        ('gr_rating rensegne',   'SELECT COUNT(*) FROM works WHERE gr_rating IS NOT NULL'),
        ('cover_url rensegne',   'SELECT COUNT(*) FROM works WHERE cover_url IS NOT NULL'),
        ('gr_reviews rensegnes', "SELECT COUNT(*) FROM works WHERE gr_reviews_text NOT IN ('null','[]','') AND gr_reviews_text IS NOT NULL"),
    ]:
        log.info(f'  {label:40s}: {sc.execute(sql).fetchone()[0]}')

    log.info(f'TERMINE {datetime.now().strftime("%H:%M:%S")} — {n_ok} OK / {n_fail} echecs / {n_done} total')
    conn.close()
    _lf.close()

asyncio.run(main())
