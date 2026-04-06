"""
26_embeddings.py
Génère les embeddings bge-m3 pour tout le corpus DP via Ollama.
Stocke dans ChromaDB (SQLite-backed) dans /app/data/chroma/.

Texte consolidé par oeuvre :
  titre + auteur + année + type + mag_title
  + synopsis + gr_summary + gr_reviews_text (3 premiers)
  + isfdb_tags + langues_vf

Cibles : toutes oeuvres avec au moins un texte disponible
"""
import fcntl, sys
_lf = open("/app/data/26.lock", "w")
try:
    fcntl.flock(_lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
except IOError:
    print("Instance deja en cours. Abandon."); sys.exit(0)

import sqlite3, json, logging, time, requests
from datetime import datetime
import chromadb

DB        = '/app/data/sf_dp.sqlite'
CHROMA    = '/app/data/chroma'
LOG_FILE  = '/app/data/26_embeddings.log'
OLLAMA    = 'http://ollama:11434'
MODEL     = 'bge-m3'
BATCH     = 50    # embeddings par batch
COMMIT_N  = 500

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()])
log = logging.getLogger()
log.info('=== 26_embeddings.py ===')

conn = sqlite3.connect(DB, timeout=60)
conn.row_factory = sqlite3.Row

# ChromaDB persistant
client = chromadb.PersistentClient(path=CHROMA)
try:
    col = client.get_collection('sf_dp')
    log.info(f'  Collection existante : {col.count()} embeddings')
except Exception:
    col = client.create_collection(
        name='sf_dp',
        metadata={'hnsw:space': 'cosine'}
    )
    log.info('  Nouvelle collection créée')

# IDs déjà dans ChromaDB
existing = set()
if col.count() > 0:
    all_ids = col.get(include=[])['ids']
    existing = set(all_ids)
    log.info(f'  {len(existing)} embeddings déjà présents')

def build_text(r):
    """Construit le texte consolidé pour l'embedding."""
    parts = []
    # Identité
    parts.append(f"{r['title']} — {r['author']} ({r['year'] or '?'})")
    if r['type']: parts.append(f"Type: {r['type']}")
    if r['mag_title']: parts.append(f"Magazine: {r['mag_title']}")
    if r['langues_vf']: parts.append(f"Traduit en: {r['langues_vf']}")
    if r['isfdb_tags']: parts.append(f"Tags: {r['isfdb_tags'][:200]}")
    # Textes enrichis
    if r['synopsis']: parts.append(r['synopsis'][:500])
    if r['gr_summary'] and r['gr_summary'] != r['synopsis']:
        parts.append(r['gr_summary'][:500])
    if r['gr_reviews_text']:
        try:
            reviews = json.loads(r['gr_reviews_text'])
            for rev in reviews[:3]:
                if len(str(rev)) > 50:
                    parts.append(str(rev)[:200])
        except Exception:
            pass
    return ' | '.join(p for p in parts if p)

def get_embedding(text):
    """Appel Ollama bge-m3."""
    r = requests.post(f'{OLLAMA}/api/embeddings',
        json={'model': MODEL, 'prompt': text[:2000]},
        timeout=30)
    return r.json().get('embedding', [])

# Cibles : oeuvres avec au moins synopsis ou gr_summary
rows = conn.execute("""
    SELECT title_id, title, author, year, "type",
           mag_title, langues_vf, isfdb_tags,
           synopsis, gr_summary, gr_reviews_text,
           dp_eu, dp_us, has_french_vf, award_count, annualviews,
           death_year
    FROM works
    WHERE (synopsis IS NOT NULL AND synopsis != '')
       OR (gr_summary IS NOT NULL AND gr_summary != '')
    ORDER BY
        CASE WHEN dp_eu=1 AND dp_us=1 THEN 0
             WHEN dp_eu=1 THEN 1
             ELSE 2 END,
        award_count DESC NULLS LAST,
        annualviews DESC NULLS LAST
""").fetchall()

targets = [r for r in rows if str(r['title_id']) not in existing]
log.info(f'  {len(targets)} oeuvres à embedder ({len(rows)} total, {len(existing)} déjà faits)')

n_done = n_ok = n_fail = 0
batch_ids, batch_embs, batch_docs, batch_metas = [], [], [], []

for row in targets:
    tid  = str(row['title_id'])
    text = build_text(row)
    if len(text) < 20:
        continue

    try:
        emb = get_embedding(text)
        if not emb or len(emb) != 1024:
            n_fail += 1
            continue

        batch_ids.append(tid)
        batch_embs.append(emb)
        batch_docs.append(text[:500])
        batch_metas.append({
            'title':       str(row['title'] or ''),
            'author':      str(row['author'] or ''),
            'year':        int(row['year'] or 0),
            'type':        str(row['type'] or ''),
            'dp_eu':       int(row['dp_eu'] or 0),
            'dp_us':       int(row['dp_us'] or 0),
            'has_vf':      int(row['has_french_vf'] or 0),
            'awards':      int(row['award_count'] or 0),
            'death_year':  int(row['death_year'] or 0),
        })
        n_ok += 1

        if len(batch_ids) >= BATCH:
            col.add(ids=batch_ids, embeddings=batch_embs,
                    documents=batch_docs, metadatas=batch_metas)
            batch_ids, batch_embs, batch_docs, batch_metas = [], [], [], []
            log.info(f'  BATCH {n_done}/{len(targets)} — ok:{n_ok} fail:{n_fail}')

    except Exception as e:
        n_fail += 1
        log.warning(f'  Erreur {tid}: {e}')

    n_done += 1

# Dernier batch
if batch_ids:
    col.add(ids=batch_ids, embeddings=batch_embs,
            documents=batch_docs, metadatas=batch_metas)

log.info('=== RESULTATS ===')
log.info(f'  Total embeddings : {col.count()}')
log.info(f'  Ajoutes          : {n_ok}')
log.info(f'  Echecs           : {n_fail}')
log.info(f'TERMINE {datetime.now().strftime("%H:%M:%S")}')
conn.close()
_lf.close()
