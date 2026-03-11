"""
14_dp_magazines.py v2
DP US + EU short fiction magazines 1928-1963.
Logique : CCE Class A individuel > UPenn contributions > compilation magazine.
Convention de Berne : duree US 28 ans non renouvelé = DP EU aussi.
"""
import fcntl, sys
_lf = open("/app/data/14.lock", "w")
try:
    fcntl.flock(_lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
except IOError:
    print("Instance deja en cours. Abandon."); sys.exit(0)

import sqlite3, requests, time, logging, re, os, glob, unicodedata
import mysql.connector
from datetime import datetime

DB       = '/app/data/sf_dp.sqlite'
LOG_FILE = '/app/data/14_magazines.log'
CCE_DIR  = '/app/data/cce-spreadsheets'
HEADERS  = {'User-Agent': 'sf-domaine-public/1.0 (public-domain-research)'}

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()])
log = logging.getLogger()
log.info('=== 14_dp_magazines.py v2 ===')

conn = sqlite3.connect(DB, timeout=30)
conn.row_factory = sqlite3.Row
sc = conn.cursor()

for col, defn in [('mag_title','TEXT'),('mag_year','INTEGER'),
                   ('mag_issn','TEXT'),('ht_mag_code','TEXT'),('dp_fr','INTEGER')]:
    try:
        sc.execute(f'ALTER TABLE works ADD COLUMN {col} {defn}')
    except Exception:
        pass
conn.commit()

# ETAPE 0 — Reset v1
log.info('=== ETAPE 0 : Reset v1 ===')
sc.execute("UPDATE works SET dp_us=NULL,dp_us_reason=NULL,dp_us_source=NULL,ht_mag_code=NULL WHERE dp_us_source='hathitrust_magazine'")
log.info(f'  {sc.rowcount} entrees v1 resetees')
conn.commit()

# ETAPE 1 — DP France prorogation de guerre
log.info('=== ETAPE 1 : dp_fr ===')
sc.execute("UPDATE works SET dp_fr=1 WHERE death_year IS NOT NULL AND death_year < 1948 AND dp_eu=1")
log.info(f'  {sc.rowcount} -> dp_fr=1')
conn.commit()

# ETAPE 2 — Contributions renouvelees UPenn
log.info('=== ETAPE 2 : UPenn contributions ===')
UPENN_SLUGS = {
    'Amazing Stories':           'amazingstories',
    'Planet Stories':            'planetstories',
    'Weird Tales':               'weirdtales',
    'Astounding Stories':        'astounding',
    'Astounding Science Fiction':'astounding',
    'Analog':                    'analogsf',
    'Galaxy':                    'galaxysf',
    'Galaxy Science Fiction':    'galaxysf',
    'Famous Fantastic Mysteries':'famousfantasticmyst',
    'Unknown':                   'unknown',
    'Unknown Worlds':            'unknown',
}
PIVOT = {
    'Amazing Stories':            (1954, 5),
    'Planet Stories':             None,
    'Weird Tales':                (1931, 2),
    'Astounding Stories':         (1933, 10),
    'Astounding Science Fiction': (1933, 10),
    'Galaxy Science Fiction':     (1953, 9),
    'Famous Fantastic Mysteries': (1940, 1),
    'Analog':                     (1960, 10),
}

def norm(s):
    s = str(s).lower().strip()
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    return re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', ' ', s)).strip()

upenn_renewed = {}
seen = set()
for mag, slug in UPENN_SLUGS.items():
    if slug in seen:
        continue
    try:
        r = requests.get(f'https://onlinebooks.library.upenn.edu/webbin/cinfo/{slug}',
                         headers=HEADERS, timeout=15)
        text = re.sub(r'<[^>]+>', ' ', r.text)
        titles = {norm(t) for t in re.findall(r'"([^"]{3,80})"', text)}
        upenn_renewed[slug] = titles
        log.info(f'  {slug}: {len(titles)} contributions renouvelees')
        seen.add(slug)
        time.sleep(0.5)
    except Exception as e:
        upenn_renewed[slug] = set()
        log.warning(f'  {slug}: {e}')

all_upenn = set()
for s in upenn_renewed.values():
    all_upenn.update(s)
log.info(f'  Total UPenn: {len(all_upenn)} contributions')

# ETAPE 3 — CCE Class A Stanford
log.info('=== ETAPE 3 : CCE Class A ===')
import csv as csv_mod
cce_titles  = set()
cce_authors = set()
for fpath in glob.glob(os.path.join(CCE_DIR, '*.csv')) + glob.glob(os.path.join(CCE_DIR, '*.tsv')):
    try:
        delim = '\t' if fpath.endswith('.tsv') else ','
        with open(fpath, encoding='utf-8', errors='replace') as f:
            for row in csv_mod.DictReader(f, delimiter=delim):
                for k, v in row.items():
                    if v and 'title'  in k.lower(): cce_titles.add(norm(v))
                    if v and 'author' in k.lower(): cce_authors.add(norm(v))
    except Exception:
        pass
log.info(f'  CCE: {len(cce_titles)} titres, {len(cce_authors)} auteurs')

# ETAPE 4 — Bulk MariaDB
log.info('=== ETAPE 4 : MariaDB bulk ===')
maria_index = {}
try:
    mc_conn = mysql.connector.connect(
        host='mariadb-sfdb', port=3306,
        user='root', password='isfdb', database='isfdb',
        connection_timeout=10)
    mc = mc_conn.cursor(dictionary=True)
    mc.execute("""
        SELECT t.title_id, t.title_title, YEAR(t.title_copyright) AS ty,
               p.pub_title AS magazine, YEAR(p.pub_year) AS py
        FROM titles t
        JOIN pub_content pc ON t.title_id = pc.title_id
        JOIN pubs p ON pc.pub_id = p.pub_id
        WHERE p.pub_ctype = 'MAGAZINE'
          AND t.title_ttype IN ('SHORTFICTION','NOVELETTE','NOVELLA')
          AND YEAR(p.pub_year) BETWEEN 1928 AND 1963
    """)
    for row in mc.fetchall():
        key = (norm(row['title_title']), row['ty'] or row['py'] or 0)
        maria_index.setdefault(key, []).append(row)
    mc_conn.close()
    log.info(f'  {len(maria_index)} titres magazines MariaDB indexes')
except Exception as e:
    log.error(f'  MariaDB: {e}')

def base_mag(s):
    if not s: return ''
    s = re.sub(r',\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec).*$', '', s, flags=re.IGNORECASE)
    s = re.sub(r',?\s*(No\.?|v\.?|Vol\.?|Winter|Spring|Summer|Fall|Autumn)\s*[\d.].*$', '', s, flags=re.IGNORECASE)
    return s.strip()

# ETAPE 5 — Application regles DP
log.info('=== ETAPE 5 : Application regles DP ===')
sc.execute("""
    SELECT title_id, title, author, year, death_year, dp_eu, dp_us
    FROM works
    WHERE year BETWEEN 1928 AND 1963
      AND dp_us IS NULL
      AND "type" IN ('short story','shortfiction','novelette','novella')
""")
targets = list(sc.fetchall())
log.info(f'  {len(targets)} short fiction a traiter')

n_dp = n_ic = 0
for row in targets:
    tid  = row['title_id']
    t_n  = norm(row['title']  or '')
    a_n  = norm(row['author'] or '')
    year = row['year'] or 0

    # Source magazine via MariaDB
    mag_name = mag_year = None
    for delta in (0, 1, -1):
        k = (t_n, year + delta)
        if k in maria_index:
            mag_name = maria_index[k][0]['magazine']
            mag_year = maria_index[k][0]['py']
            break
    mb   = base_mag(mag_name)
    slug = UPENN_SLUGS.get(mb, '')

    in_cce       = t_n in cce_titles
    in_upenn     = t_n in all_upenn
    in_mag_upenn = bool(slug) and t_n in upenn_renewed.get(slug, set())
    auth_in_cce  = a_n in cce_authors

    # Convention de Berne : non renouvelé = durée US 28 ans = DP EU par réciprocité
    berne_dp_eu = (not in_cce) and (not in_upenn) and (year + 28 < 2026)

    if in_cce or in_upenn or in_mag_upenn:
        reason = f'Protege — renouvellement trouve CCE={in_cce} UPenn={in_upenn} mag={in_mag_upenn}'
        sc.execute(
            "UPDATE works SET dp_us=0,dp_us_reason=?,dp_us_source='cce_upenn_magazine',mag_title=?,mag_year=? WHERE title_id=?",
            (reason, mag_name, mag_year, tid))
        n_ic += 1
    else:
        pivot = PIVOT.get(mb)
        if pivot is None:
            comp = 'compilation jamais renouvelee (DP)'
        elif isinstance(pivot, tuple):
            pub_d = (mag_year or year) * 12 + 1
            piv_d = pivot[0] * 12 + pivot[1]
            comp  = 'compilation DP' if pub_d < piv_d else 'compilation protegee mais nouvelle non renouvelee'
        else:
            comp = ''
        berne = ' Convention de Berne: duree US 28 ans => DP EU aussi.' if berne_dp_eu else ''
        reason = (f'DP US — non trouve CCE Class A ni UPenn'
                  f'{" (in "+mb+" "+str(mag_year)+")" if mb else ""}. '
                  f'{comp}.{berne}')
        sc.execute(
            "UPDATE works SET dp_us=1,dp_us_reason=?,dp_us_source='cce_magazine_shortfiction',mag_title=?,mag_year=? WHERE title_id=?",
            (reason, mag_name, mag_year, tid))
        if berne_dp_eu and not row['dp_eu']:
            sc.execute("UPDATE works SET dp_eu=1 WHERE title_id=?", (tid,))
        n_dp += 1

    if row['death_year'] and int(row['death_year']) < 1948 and row['dp_eu']:
        sc.execute("UPDATE works SET dp_fr=1 WHERE title_id=?", (tid,))

conn.commit()
log.info(f'  -> dp_us=1 : {n_dp}')
log.info(f'  -> dp_us=0 : {n_ic}')

# ETAPE 6 — Stats finales
log.info('=== STATS FINALES ===')
for label, sql in [
    ('dp_us=1 total',           "SELECT COUNT(*) FROM works WHERE dp_us=1"),
    ('dp_us=1 short fiction',   "SELECT COUNT(*) FROM works WHERE dp_us=1 AND \"type\" IN ('short story','shortfiction','novelette','novella')"),
    ('dp_us=1 sf sans VF',      "SELECT COUNT(*) FROM works WHERE dp_us=1 AND has_french_vf=0 AND \"type\" IN ('short story','shortfiction','novelette','novella')"),
    ('dp_eu=1 AND dp_us=1 sVF', "SELECT COUNT(*) FROM works WHERE dp_eu=1 AND dp_us=1 AND has_french_vf=0"),
    ('dp_fr=1',                 "SELECT COUNT(*) FROM works WHERE dp_fr=1"),
    ('source cce_magazine',     "SELECT COUNT(*) FROM works WHERE dp_us_source='cce_magazine_shortfiction'"),
    ('dp_us=NULL restant',      "SELECT COUNT(*) FROM works WHERE dp_us IS NULL AND year BETWEEN 1928 AND 1963"),
]:
    sc.execute(sql)
    log.info(f'  {label:45s}: {sc.fetchone()[0]}')

log.info('\n  Top nouvelles DP sans VF primees :')
sc.execute("""
    SELECT title, author, year, mag_title, awards
    FROM works
    WHERE dp_us=1 AND has_french_vf=0
      AND "type" IN ('short story','shortfiction','novelette','novella')
      AND award_count > 0
    ORDER BY award_count DESC, annualviews DESC NULLS LAST
    LIMIT 20
""")
for r in sc.fetchall():
    log.info(f"  [{r[2]}] {r[1]} — {r[0]}{' (in '+str(r[3])+')' if r[3] else ''}")
    if r[4]:
        log.info(f"        {str(r[4])[:80]}")

log.info(f'\n✅ Termine a {datetime.now().strftime("%H:%M:%S")}')
conn.close()
_lf.close()
