import fcntl, sys
_lf = open("/app/data/12.lock", "w")
try:
    fcntl.flock(_lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
except IOError:
    print("Instance deja en cours. Abandon.")
    sys.exit(0)

"""
12_dp_us_check.py v2
"""
import sqlite3, requests, time, logging, re, csv, io, urllib.parse
from datetime import datetime

DB       = '/app/data/sf_dp.sqlite'
LOG_FILE = '/app/data/dp_check.log'
HEADERS  = {'User-Agent': 'sf-domaine-public/1.0 (public-domain-research)'}

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()])
log = logging.getLogger()

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur  = conn.cursor()

for col, defn in [
    ('dp_us_source','TEXT'),('ht_rights_code','TEXT'),('ht_id','TEXT'),
    ('ol_oclc','TEXT'),('lccn','TEXT'),('dp_checked','INTEGER DEFAULT 0'),
]:
    try: cur.execute(f'ALTER TABLE works ADD COLUMN {col} {defn}')
    except: pass
conn.commit()

def normalize(t):
    t = str(t).lower().strip()
    t = re.sub(r'[^\w\s]',' ',t)
    return re.sub(r'\s+',' ',t).strip()

def titles_match(a,b,threshold=0.7):
    a,b = normalize(a),normalize(b)
    if a==b: return True
    if a[:15] in b or b[:15] in a: return True
    wa,wb = set(a.split()),set(b.split())
    if not wa or not wb: return False
    return len(wa&wb)/len(wa|wb)>=threshold

def checkpoint(n,every=500):
    if n%every==0: conn.commit(); log.info(f"  checkpoint {n}")

HT_DP_CODES = {'pd','pdus','cc-zero','cc-by','cc-by-sa','cc-by-nd','cc-by-nc','cc-by-nc-sa'}
HT_IC_CODES = {'ic','icus','ic-world'}

# ETAPE 1 — Romans non trouvés CCE → DP US confirmé
log.info("=== ETAPE 1 : Romans non trouvés CCE → dp_us=1 ===")
cur.execute("SELECT COUNT(*) FROM works WHERE \"type\"='novel' AND year BETWEEN 1928 AND 1963 AND dp_us IS NULL AND dp_us_reason LIKE '%non trouvé%'")
log.info(f"  {cur.fetchone()[0]} romans concernés")
cur.execute("""UPDATE works SET dp_us=1,
    dp_us_reason='DP US — non renouvelé (Stanford CCE Class A, livres 1923-1963)',
    dp_us_source='cce_stanford_novel'
    WHERE "type"='novel' AND year BETWEEN 1928 AND 1963
    AND dp_us IS NULL AND dp_us_reason LIKE '%non trouvé%'""")
conn.commit()
log.info(f"  ✅ {cur.rowcount} romans → dp_us=1")

# ETAPE 2 — NYPL CCE extended
log.info("\n=== ETAPE 2 : NYPL CCE extended ===")
nypl_titles = set()
try:
    r = requests.get("https://raw.githubusercontent.com/NYPL/cce-renewals/master/renewals.tsv",
                     headers=HEADERS, timeout=60)
    reader = csv.DictReader(io.StringIO(r.content.decode('utf-8',errors='replace')), delimiter='\t')
    for row in reader:
        t = row.get('title','') or row.get('Title','')
        if t: nypl_titles.add(normalize(t))
    log.info(f"  {len(nypl_titles)} titres renouvelés NYPL")
except Exception as e:
    log.warning(f"  NYPL échec: {e}")

if nypl_titles:
    cur.execute("SELECT title_id,title FROM works WHERE year BETWEEN 1928 AND 1963 AND dp_us IS NULL")
    nypl_ic=0
    for row in cur.fetchall():
        if normalize(row['title']) in nypl_titles:
            cur.execute("UPDATE works SET dp_us=0,dp_us_reason='Protégé — renouvellement NYPL CCE',dp_us_source='nypl_cce' WHERE title_id=?",(row['title_id'],))
            nypl_ic+=1
    conn.commit()
    log.info(f"  ✅ {nypl_ic} protégés identifiés")

# ETAPE 3 — HathiTrust via Open Library OCLC
log.info("\n=== ETAPE 3 : Open Library → OCLC → HathiTrust ===")
cur.execute("""SELECT title_id,title,author,year FROM works
    WHERE year BETWEEN 1928 AND 1963 AND dp_us IS NULL
    AND (ol_oclc IS NULL OR ol_oclc='')
    ORDER BY award_count DESC, annualviews DESC NULLS LAST LIMIT 8000""")
ol_targets = list(cur.fetchall())
log.info(f"  {len(ol_targets)} œuvres sans OCLC")
ol_found=0
for i,row in enumerate(ol_targets):
    try:
        r=requests.get('https://openlibrary.org/search.json',headers=HEADERS,timeout=10,
                       params={'title':row['title'],'author':row['author'],'limit':3,'fields':'key,title,oclc,lccn'})
        for doc in r.json().get('docs',[]):
            if not titles_match(row['title'],doc.get('title','')): continue
            oclc=doc.get('oclc',[]); lccn=doc.get('lccn',[])
            if oclc or lccn:
                cur.execute("UPDATE works SET ol_oclc=?,lccn=? WHERE title_id=?",
                            (oclc[0] if oclc else None,lccn[0] if lccn else None,row['title_id']))
                ol_found+=1
            break
        checkpoint(i+1); time.sleep(0.25)
    except: pass
conn.commit()
log.info(f"  ✅ {ol_found} OCLC récupérés")

cur.execute("""SELECT title_id,title,ol_oclc,lccn FROM works
    WHERE year BETWEEN 1928 AND 1963 AND dp_us IS NULL
    AND (ol_oclc IS NOT NULL OR lccn IS NOT NULL)""")
ht_targets=list(cur.fetchall())
log.info(f"  {len(ht_targets)} œuvres → HathiTrust")
ht_dp=ht_ic=ht_err=0
for i,row in enumerate(ht_targets):
    oclc=row['ol_oclc']; lccn=row['lccn']
    id_type='oclc' if oclc else 'lccn'
    id_val=(oclc or lccn or '').strip()
    if not id_val: continue
    try:
        r=requests.get(f'https://catalog.hathitrust.org/api/volumes/brief/{id_type}/{id_val}.json',
                       headers=HEADERS,timeout=10)
        items=r.json().get('items',[])
        if not items: continue
        codes=[it.get('rightsCode','') for it in items]
        best=codes[0]; htid=items[0].get('htid','')
        if any(c in HT_DP_CODES for c in codes):
            cur.execute("UPDATE works SET dp_us=1,dp_us_reason=?,dp_us_source='hathitrust',ht_rights_code=?,ht_id=? WHERE title_id=?",
                        (f'DP US — HathiTrust:{best}',best,htid,row['title_id'])); ht_dp+=1
        elif any(c in HT_IC_CODES for c in codes):
            cur.execute("UPDATE works SET dp_us=0,dp_us_reason=?,dp_us_source='hathitrust',ht_rights_code=?,ht_id=? WHERE title_id=?",
                        (f'Protégé — HathiTrust:{best}',best,htid,row['title_id'])); ht_ic+=1
        checkpoint(i+1); time.sleep(0.25)
    except Exception as e:
        ht_err+=1
        if ht_err<=3: log.warning(f"  HT err {row['title_id']}: {e}")
conn.commit()
log.info(f"  ✅ HathiTrust: {ht_dp} DP, {ht_ic} protégés, {ht_err} erreurs")

# ETAPE 4 — Marquage final
cur.execute("""UPDATE works SET dp_checked=1,
    dp_us_reason=CASE WHEN dp_us IS NULL AND year BETWEEN 1928 AND 1963
        THEN 'DP US probable — non trouvé CCE/NYPL/HathiTrust. Vérifier : https://cocatalog.loc.gov'
        ELSE dp_us_reason END
    WHERE year BETWEEN 1928 AND 1963""")
conn.commit()

# STATS
log.info("\n=== STATS FINALES ===")
for label,sql in [
    ("Romans 1928-63 dp_us=1",  "SELECT COUNT(*) FROM works WHERE \"type\"='novel' AND year BETWEEN 1928 AND 1963 AND dp_us=1"),
    ("Romans 1928-63 dp_us=0",  "SELECT COUNT(*) FROM works WHERE \"type\"='novel' AND year BETWEEN 1928 AND 1963 AND dp_us=0"),
    ("Romans 1928-63 dp_us=NULL","SELECT COUNT(*) FROM works WHERE \"type\"='novel' AND year BETWEEN 1928 AND 1963 AND dp_us IS NULL"),
    ("Source cce_stanford_novel","SELECT COUNT(*) FROM works WHERE dp_us_source='cce_stanford_novel'"),
    ("Source nypl_cce",         "SELECT COUNT(*) FROM works WHERE dp_us_source='nypl_cce'"),
    ("Source hathitrust",       "SELECT COUNT(*) FROM works WHERE dp_us_source='hathitrust'"),
    ("DP sans VF total",        "SELECT COUNT(*) FROM works WHERE (dp_eu=1 OR dp_us=1) AND has_french_vf=0"),
    ("DP sans VF awards",       "SELECT COUNT(*) FROM works WHERE (dp_eu=1 OR dp_us=1) AND has_french_vf=0 AND award_count>0"),
]:
    cur.execute(sql); log.info(f"  {label:40s}: {cur.fetchone()[0]}")

log.info("\n  Top 20 romans Hugo/Nebula nouvellement DP :")
cur.execute("""SELECT title,author,year,awards FROM works
    WHERE dp_us=1 AND dp_us_source='cce_stanford_novel'
    AND has_french_vf=0 AND award_count>0
    ORDER BY award_count DESC,annualviews DESC NULLS LAST LIMIT 20""")
for row in cur.fetchall():
    log.info(f"  [{row[2]}] {row[1]} — {row[0]}")
    if row[3]: log.info(f"        {row[3][:80]}")

log.info(f"\n✅ Terminé {datetime.now().strftime('%H:%M:%S')}")
conn.close()
