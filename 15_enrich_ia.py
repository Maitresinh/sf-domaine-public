
import sqlite_utils, requests, time, logging, re

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s  %(message)s', datefmt='%H:%M:%S')
log = logging.getLogger()
DB   = '/app/data/sf_dp.sqlite'
WAIT = 2.0
db = sqlite_utils.Database(DB)

for col, typ in [('ia_identifier','TEXT'),('ia_downloads','INTEGER'),('ia_has_text','INTEGER'),('ia_searched','INTEGER')]:
    try: db.execute(f'ALTER TABLE works ADD COLUMN {col} {typ}')
    except: pass

targets = list(db.execute('''
    SELECT title_id, title, author, year FROM works
    WHERE has_french_vf=0 AND dp_eu=1 AND dp_us=1
    AND (ia_searched IS NULL OR ia_searched=0)
    ORDER BY award_count DESC NULLS LAST, annualviews DESC NULLS LAST
''').fetchall())
log.info(f'Cibles IA : {len(targets)}')

found = errors = 0
for i, (tid, title, author, year) in enumerate(targets):
    title_clean  = re.sub(r'[^\w\s]', ' ', str(title)).strip()
    author_last  = str(author).split()[-1] if author else ''
    query = f'title:({title_clean}) AND creator:({author_last}) AND mediatype:(texts)'
    try:
        r = requests.get('https://archive.org/advancedsearch.php',
            params={'q':query,'fl[]':['identifier','downloads','format'],'rows':3,'page':1,'output':'json'},
            timeout=10, headers={'User-Agent':'sf-dp-editorial/1.0'})
        r.raise_for_status()
        docs = r.json().get('response',{}).get('docs',[])
        best = max(docs, key=lambda d: d.get('downloads',0) or 0) if docs else None
        if best:
            fmts     = best.get('format',[])
            has_text = 1 if any(f in str(fmts) for f in ['DjVu','Text','PDF','EPUB']) else 0
            db.execute('UPDATE works SET ia_identifier=?,ia_downloads=?,ia_has_text=?,ia_searched=1 WHERE title_id=?',
                [best.get('identifier'), best.get('downloads',0) or 0, has_text, tid])
            found += 1
            if i % 200 == 0: log.info(f'[{i+1}/{len(targets)}] {author} — {title} → {best.get("identifier")} ({best.get("downloads",0)} dl)')
        else:
            db.execute('UPDATE works SET ia_searched=1 WHERE title_id=?',[tid])
        db.conn.commit()
    except Exception as e:
        errors += 1
        db.execute('UPDATE works SET ia_searched=1 WHERE title_id=?',[tid])
        db.conn.commit()
    time.sleep(WAIT)
    if (i+1) % 500 == 0:
        n = db.execute('SELECT COUNT(*) FROM works WHERE ia_identifier IS NOT NULL').fetchone()[0]
        log.info(f'Checkpoint {i+1} — {n} trouvés')

n_id   = db.execute('SELECT COUNT(*) FROM works WHERE ia_identifier IS NOT NULL').fetchone()[0]
n_text = db.execute('SELECT COUNT(*) FROM works WHERE ia_has_text=1').fetchone()[0]
log.info(f'FINAL: {n_id} identifiants, {n_text} textes, {errors} erreurs')
