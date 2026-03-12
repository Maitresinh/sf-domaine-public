
import sqlite_utils, requests, time, logging, re, json
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s  %(message)s', datefmt='%H:%M:%S')
log = logging.getLogger()
DB   = '/app/data/sf_dp.sqlite'
WAIT = 15
db = sqlite_utils.Database(DB)

HEADERS_LIST = [
    {'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36'},
    {'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/605.1.15 Version/17.2 Safari/605.1.15'},
    {'User-Agent':'Mozilla/5.0 (X11; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0'},
]
_ua = [0]
def hdrs():
    h = HEADERS_LIST[_ua[0] % len(HEADERS_LIST)]; _ua[0] += 1; return h

def search_gr(title, author):
    q   = f'{title} {author.split()[-1]}'
    url = 'https://www.goodreads.com/search?q=' + requests.utils.quote(q)
    r   = requests.get(url, headers=hdrs(), timeout=15)
    if r.status_code != 200: return None, r.status_code
    soup = BeautifulSoup(r.text, 'html.parser')
    link = soup.select_one('a.bookTitle')
    if link: return 'https://www.goodreads.com' + link['href'].split('?')[0], 200
    return None, 404

def scrape_gr(url):
    r = requests.get(url, headers=hdrs(), timeout=15)
    if r.status_code != 200: return None
    soup   = BeautifulSoup(r.text, 'html.parser')
    result = {}
    el = soup.select_one('div.RatingStatistics__rating')
    if el:
        try: result['gr_rating'] = float(el.text.strip())
        except: pass
    el = soup.select_one('span[data-testid="ratingsCount"]')
    if el:
        v = re.sub(r'[^\d]','',el.text)
        if v: result['gr_votes'] = int(v)
    el = soup.select_one('div.BookPageMetadataSection__description span.Formatted')
    if el: result['gr_summary'] = el.text.strip()[:600]
    revs = [r.text.strip()[:300] for r in soup.select('section.ReviewText span.Formatted')[:3] if len(r.text.strip())>50]
    if revs: result['gr_reviews_text'] = json.dumps(revs, ensure_ascii=False)
    return result or None

targets = list(db.execute('''
    SELECT title_id, title, author, year, award_count FROM works
    WHERE has_french_vf=0 AND dp_eu=1 AND dp_us=1 AND award_count>0
    AND (gr_searched IS NULL OR gr_searched=0)
    ORDER BY award_count DESC, annualviews DESC NULLS LAST
''').fetchall())
log.info(f'Cibles GR : {len(targets)}')

found = blocked = 0
for i, (tid, title, author, year, aw) in enumerate(targets):
    log.info(f'[{i+1}/{len(targets)}] {author} — {title}')
    try:
        url, status = search_gr(title, author)
        time.sleep(WAIT)
        if status == 429:
            log.warning('Rate limited — pause 60s'); blocked += 1; time.sleep(60)
            db.execute('UPDATE works SET gr_searched=1 WHERE title_id=?',[tid]); db.conn.commit(); continue
        if not url:
            db.execute('UPDATE works SET gr_searched=1 WHERE title_id=?',[tid]); db.conn.commit(); continue
        log.info(f'  {url}')
        data = scrape_gr(url)
        time.sleep(WAIT)
        if data:
            data['gr_searched'] = 1
            db['works'].update(tid, data)
            found += 1
            log.info(f'  ✅ rating={data.get("gr_rating","?")} votes={data.get("gr_votes","?")}')
        else:
            db.execute('UPDATE works SET gr_searched=1 WHERE title_id=?',[tid])
        db.conn.commit()
    except Exception as e:
        if '429' in str(e) or '403' in str(e):
            log.warning(f'Bloqué — pause 120s'); blocked += 1; time.sleep(120)
        else:
            log.warning(f'Erreur {tid}: {e}')
        db.execute('UPDATE works SET gr_searched=1 WHERE title_id=?',[tid]); db.conn.commit()

n = db.execute("SELECT COUNT(*) FROM works WHERE gr_rating IS NOT NULL AND gr_rating!=''").fetchone()[0]
log.info(f'FINAL: {found} trouvés, {n} avec rating, {blocked} bloqués')
