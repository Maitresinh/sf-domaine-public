"""
23_editions_json.py
Pré-calcule les éditions par langue pour chaque œuvre du catalogue prioritaire.
Stocke un JSON compact dans works.editions_json.

Format JSON :
[
  {"lang": "French", "lang_code": "fr", "title": "...", "first_year": 1952,
   "last_year": 2009, "nb_ed": 6, "publishers": "Gallimard | Le Livre de Poche",
   "translator": "Jean Dupont"},
  ...
]

Source : MariaDB ISFDB — titles.title_parent + title_language + pub_content + pubs
Traducteurs : author_language=lang_id OU notes {{Tr|}}
"""
import fcntl, sys
_lf = open("/app/data/23.lock", "w")
try:
    fcntl.flock(_lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
except IOError:
    print("Instance deja en cours. Abandon."); sys.exit(0)

import sqlite3, json, re, logging, time
import mysql.connector
from datetime import datetime

DB        = '/app/data/sf_dp.sqlite'
LOG_FILE  = '/app/data/23_editions.log'
COMMIT_N  = 500
BATCH_SQL = 2000   # titres par requête MariaDB

# Langues à inclure (exclure anglais=17 qui est la VO)
LANG_EN   = 17
# Codes ISO pour affichage
LANG_ISO  = {
    22: 'fr', 26: 'de', 36: 'it', 16: 'nl', 59: 'es', 53: 'pt',
    54: 'ro', 37: 'ja', 55: 'ru', 62: 'sv', 32: 'hu', 31: 'hr',
    52: 'pl', 60: 'sr', 21: 'fi', 10: 'bg', 14: 'cs', 67: 'tr',
    27: 'el', 17: 'en',
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()])
log = logging.getLogger()
log.info('=== 23_editions_json.py ===')

# ── Connexions ────────────────────────────────────────────────────────────────
sc = sqlite3.connect(DB, timeout=60)
sc.row_factory = sqlite3.Row

mc = mysql.connector.connect(
    host='mariadb-sfdb', port=3306,
    user='root', password='isfdb', database='isfdb',
    connection_timeout=15)
cur = mc.cursor(dictionary=True)

# ── Colonne editions_json ─────────────────────────────────────────────────────
try:
    sc.execute('ALTER TABLE works ADD COLUMN editions_json TEXT')
    sc.commit()
    log.info('  Colonne editions_json créée')
except Exception:
    log.info('  Colonne editions_json déjà présente')

# ── Cibles : catalogue prioritaire + toutes œuvres avec langues_vf ────────────
log.info('  Chargement cibles...')
rows = sc.execute("""
    SELECT title_id, title, year
    FROM works
    WHERE (
        (dp_eu=1 AND dp_us=1)
        OR nb_langues_vf > 0
    )
    AND editions_json IS NULL
    ORDER BY award_count DESC NULLS LAST, annualviews DESC NULLS LAST
""").fetchall()
targets = [(r['title_id'], r['title'], r['year']) for r in rows]
log.info(f'  {len(targets)} œuvres à traiter')

# ── Traducteurs via notes {{Tr|}} ─────────────────────────────────────────────
log.info('  Chargement notes traducteurs MariaDB...')
cur.execute("""
    SELECT t.title_parent AS orig_id, t.title_language AS lang_id,
           n.note_note AS note
    FROM titles t
    JOIN notes n ON n.note_id = t.note_id
    WHERE t.title_parent > 0
      AND n.note_note LIKE '%{Tr|%'
""")
tr_notes = {}  # (orig_id, lang_id) -> traducteur
for r in cur.fetchall():
    matches = re.findall(r'\{\{Tr\|([^}]+)\}\}', r['note'], re.IGNORECASE)
    trad = ' / '.join(m.strip() for m in matches if m.strip() and '{{' not in m)
    if trad:
        key = (r['orig_id'], r['lang_id'])
        if key not in tr_notes:
            tr_notes[key] = trad
log.info(f'  {len(tr_notes)} traducteurs via notes')

def parse_year(d):
    """Extrait l'année depuis une date MariaDB (YYYY-MM-DD ou 0000-00-00)."""
    if not d: return None
    s = str(d)[:4]
    try:
        y = int(s)
        return y if y > 1000 else None
    except Exception:
        return None

def clean_publishers(s):
    """Déduplique et nettoie la liste des éditeurs."""
    if not s: return ''
    parts = [p.strip() for p in s.split('|')]
    seen, out = set(), []
    for p in parts:
        if p and p not in seen:
            seen.add(p); out.append(p)
    return ' | '.join(out[:5])  # max 5 éditeurs

def strip_part(title):
    """Supprime les suffixes (Part X of Y) pour regrouper les feuilletons."""
    return re.sub(r'\s*\(Part\s+\d+\s+of\s+\d+\)', '', title, flags=re.IGNORECASE).strip()

# ── Requête MariaDB par batch ──────────────────────────────────────────────────
n_done = n_found = n_empty = 0

for i in range(0, len(targets), BATCH_SQL):
    batch = targets[i:i+BATCH_SQL]
    ids   = [t[0] for t in batch]
    ph    = ','.join(['%s'] * len(ids))

    cur.execute(f"""
        SELECT
            t.title_parent                                          AS orig_id,
            t.title_language                                        AS lang_id,
            l.lang_name                                             AS lang_name,
            t.title_title                                           AS title_raw,
            MIN(p.pub_year)                                         AS first_year,
            MAX(p.pub_year)                                         AS last_year,
            COUNT(DISTINCT p.pub_id)                                AS nb_ed,
            GROUP_CONCAT(DISTINCT pub.publisher_name
                ORDER BY p.pub_year SEPARATOR ' | ')                AS editeurs,
            GROUP_CONCAT(DISTINCT
                CASE WHEN a.author_language = t.title_language
                     THEN a.author_canonical END
                SEPARATOR ' / ')                                    AS traducteur
        FROM titles t
        JOIN languages l          ON l.lang_id       = t.title_language
        JOIN pub_content pc       ON pc.title_id     = t.title_id
        JOIN pubs p               ON p.pub_id        = pc.pub_id
        JOIN publishers pub       ON pub.publisher_id = p.publisher_id
        LEFT JOIN canonical_author ca ON ca.title_id = t.title_id
                                     AND ca.ca_status = 1
        LEFT JOIN authors a       ON a.author_id     = ca.author_id
        WHERE t.title_parent IN ({ph})
          AND t.title_language != {LANG_EN}
          AND p.pub_year IS NOT NULL
          AND p.pub_year != '0000-00-00'
        GROUP BY t.title_parent, t.title_language, t.title_title
        ORDER BY t.title_parent, t.title_language, MIN(p.pub_year)
    """, ids)

    # Regrouper par orig_id
    raw = {}
    for r in cur.fetchall():
        oid  = r['orig_id']
        lid  = r['lang_id']
        if oid not in raw:
            raw[oid] = {}

        # Regrouper les feuilletons : même lang, titre de base identique
        base_title = strip_part(r['title_raw'])
        key = (lid, base_title)
        if key not in raw[oid]:
            raw[oid][key] = {
                'lang':       r['lang_name'],
                'lang_code':  LANG_ISO.get(lid, '??'),
                'title':      base_title,
                'first_year': parse_year(r['first_year']),
                'last_year':  parse_year(r['last_year']),
                'nb_ed':      r['nb_ed'],
                'publishers': clean_publishers(r['editeurs']),
                'translator': r['traducteur'] or tr_notes.get((oid, lid), ''),
            }
        else:
            # Fusionner feuilleton
            entry = raw[oid][key]
            fy = parse_year(r['first_year'])
            ly = parse_year(r['last_year'])
            if fy and (not entry['first_year'] or fy < entry['first_year']):
                entry['first_year'] = fy
            if ly and (not entry['last_year'] or ly > entry['last_year']):
                entry['last_year'] = ly
            entry['nb_ed'] += r['nb_ed']
            if r['traducteur'] and not entry['translator']:
                entry['translator'] = r['traducteur']
            # Enrichir traducteur depuis notes si manquant
            if not entry['translator']:
                entry['translator'] = tr_notes.get((oid, lid), '')

    # ── Écrire dans SQLite ────────────────────────────────────────────────────
    for tid, title, year in batch:
        if tid in raw and raw[tid]:
            # Trier : FR en premier, puis par langue, puis par first_year
            editions = sorted(
                raw[tid].values(),
                key=lambda x: (0 if x['lang_code'] == 'fr' else 1, x['lang'], x['first_year'] or 9999)
            )
            j = json.dumps(editions, ensure_ascii=False, separators=(',', ':'))
            sc.execute('UPDATE works SET editions_json=? WHERE title_id=?', (j, tid))
            n_found += 1
        else:
            # Pas de traduction → JSON vide []
            sc.execute("UPDATE works SET editions_json='[]' WHERE title_id=?", (tid,))
            n_empty += 1
        n_done += 1

    if n_done % COMMIT_N == 0:
        sc.commit()
        log.info(f'  💾 {n_done}/{len(targets)} — trouvés: {n_found}, vides: {n_empty}')

sc.commit()

# ── Stats finales ─────────────────────────────────────────────────────────────
log.info('=== RÉSULTATS ===')
for label, sql in [
    ('editions_json renseigné',   "SELECT COUNT(*) FROM works WHERE editions_json IS NOT NULL"),
    ('avec au moins 1 traduction',"SELECT COUNT(*) FROM works WHERE editions_json IS NOT NULL AND editions_json != '[]'"),
    ('avec VF française',         "SELECT COUNT(*) FROM works WHERE editions_json LIKE '%\"lang_code\":\"fr\"%'"),
]:
    log.info(f'  {label:40s}: {sc.execute(sql).fetchone()[0]}')

# Exemple
log.info('\n  Exemples :')
for r in sc.execute("""
    SELECT title, author, editions_json FROM works
    WHERE editions_json IS NOT NULL AND editions_json != '[]'
    AND dp_eu=1 AND dp_us=1 AND has_french_vf=1
    ORDER BY annualviews DESC NULLS LAST LIMIT 3
""").fetchall():
    eds = json.loads(r[2])
    log.info(f'  {r[1]} — {r[0]} ({len(eds)} langues)')
    for e in eds[:3]:
        log.info(f'    [{e["lang_code"]}] {e["title"]} ({e["first_year"]}–{e["last_year"]}) — {e["publishers"][:50]} — trad: {e["translator"] or "?"}')

log.info(f'\n✅ Terminé à {datetime.now().strftime("%H:%M:%S")}')
sc.close(); mc.close(); _lf.close()
