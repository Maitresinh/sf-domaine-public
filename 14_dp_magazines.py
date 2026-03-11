"""
14_dp_magazines.py
Vérification DP US des short fiction publiées en magazines (1928-1963).

Stratégie :
  Pour chaque titre SQLite dp_us=NULL dans un magazine MariaDB :
    1. Retrouver le magazine + numéro via pub_content → pubs → magazine
    2. Interroger HathiTrust par ISSN ou titre magazine + année
    3. Si rightsCode pd/pdus → dp_us=1 sur les titres du numéro dans SQLite
    4. Si rightsCode ic/icus → dp_us=0

Volume : ~215 cibles identifiées (croisement SQLite ↔ MariaDB session 3)

Lancer :
  docker exec -d sf-dp-tools bash -c \
    "python3 /app/14_dp_magazines.py >> /app/data/14_magazines.log 2>&1 && echo DONE >> /app/data/14_magazines.log"
  tail -f /mnt/user/sf-dp/data/14_magazines.log
"""
import fcntl, sys
_lf = open("/app/data/14.lock", "w")
try:
    fcntl.flock(_lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
except IOError:
    print("Instance déjà en cours. Abandon.")
    sys.exit(0)

import sqlite3, requests, time, logging, re
import mysql.connector
from datetime import datetime

DB         = '/app/data/sf_dp.sqlite'
LOG_FILE   = '/app/data/14_magazines.log'
HEADERS    = {'User-Agent': 'sf-domaine-public/1.0 (public-domain-research)'}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)
log = logging.getLogger()

# ── ISSNs connus des grands pulps SF (source : ISSN Portal) ──────────────────
# Seuls les magazines avec items pd/pdus sur HathiTrust sont utiles.
# Les grands éditeurs (Street & Smith, Ziff-Davis) ont généralement renouvelé
# le copyright de compilation → ic. Mais les petits magazines souvent non.
MAGAZINE_ISSNS = {
    'Weird Tales':                    '0043-1923',
    'Amazing Stories':                '0002-7049',
    'Galaxy Science Fiction':         '0016-4240',
    'The Magazine of Fantasy and Science Fiction': '1046-1972',
    'Thrilling Wonder Stories':       '0040-7461',
    'Fantastic Adventures':           '0014-5610',
    'New Worlds':                     '0028-6079',
    'Astounding Science Fiction':     '0004-8658',
    'Astounding Stories':             '0004-8658',
    'Planet Stories':                 '0032-0951',
    'Super Science Stories':          '0039-6079',
    'Startling Stories':              '0038-9129',
    'Unknown':                        '0041-5103',
    'Unknown Worlds':                 '0041-5103',
    'Argosy':                         '0362-7039',
    'Famous Fantastic Mysteries':     '0014-5637',
    'Fantastic Story Magazine':       '0014-5610',
    'Other Worlds Science Stories':   None,
    'Science Fiction Adventures':     None,
}

HT_DP_CODES = {'pd', 'pdus', 'cc-zero', 'cc-by', 'cc-by-sa'}
HT_IC_CODES = {'ic', 'icus', 'ic-world'}

# Cache HathiTrust par ISSN+année pour éviter les doublons d'appels
ht_cache = {}  # (issn_or_title, year) → rightsCode ou None


def ht_check_issn(issn, year):
    """Vérifie le statut HathiTrust d'un magazine via son ISSN.
    Retourne 'pd', 'ic', ou None si inconnu."""
    key = (issn, year)
    if key in ht_cache:
        return ht_cache[key]
    try:
        r = requests.get(
            f'https://catalog.hathitrust.org/api/volumes/brief/issn/{issn}.json',
            headers=HEADERS, timeout=12
        )
        items = r.json().get('items', [])
        if not items:
            ht_cache[key] = None
            return None

        # Chercher un item correspondant à l'année (±1 an de tolérance)
        year_matches = []
        for it in items:
            cron = it.get('enumcron', '') or ''
            # Extraire une année depuis enumcron (ex: "v.12 no.3 1942")
            years_found = re.findall(r'\b(19[0-9]{2}|192[0-9])\b', cron)
            for y in years_found:
                if abs(int(y) - year) <= 1:
                    year_matches.append(it.get('rightsCode', ''))

        if year_matches:
            # Si au moins un item pd → le numéro est DP
            if any(c in HT_DP_CODES for c in year_matches):
                ht_cache[key] = 'pd'
                return 'pd'
            elif all(c in HT_IC_CODES for c in year_matches):
                ht_cache[key] = 'ic'
                return 'ic'

        # Pas de match d'année précis → regarder le statut global de l'ISSN
        all_codes = [it.get('rightsCode', '') for it in items]
        pd_count = sum(1 for c in all_codes if c in HT_DP_CODES)
        ic_count = sum(1 for c in all_codes if c in HT_IC_CODES)

        # Si > 50% pd et année compatible avec période DP → pd probable
        result = None
        if pd_count > ic_count:
            result = 'pd_probable'
        elif ic_count > pd_count:
            result = 'ic'

        ht_cache[key] = result
        return result

    except Exception as e:
        log.warning(f'  HT ISSN err ({issn}, {year}): {e}')
        ht_cache[key] = None
        return None


def ht_check_title(mag_title, year):
    """Fallback : recherche HathiTrust par titre magazine."""
    key = (mag_title, year)
    if key in ht_cache:
        return ht_cache[key]
    try:
        # API bibliographique HathiTrust
        q = mag_title.replace(' ', '+')
        r = requests.get(
            f'https://catalog.hathitrust.org/Search/Home?lookfor={q}&type=title&view=list&format=json',
            headers=HEADERS, timeout=12
        )
        # Pas de réponse JSON standard → essayer l'API volumes brief par titre
        # On utilise plutôt le catalog search
        data = r.json() if r.headers.get('content-type','').startswith('application/json') else {}
        ht_cache[key] = None
        return None
    except Exception:
        ht_cache[key] = None
        return None


# ── Connexions DB ─────────────────────────────────────────────────────────────
log.info('=== 14_dp_magazines.py — démarrage ===')

sqlite_conn = sqlite3.connect(DB, timeout=30)
sqlite_conn.row_factory = sqlite3.Row
sc = sqlite_conn.cursor()

try:
    maria_conn = mysql.connector.connect(
        host='mariadb-sfdb', port=3306,
        user='root', password='isfdb', database='isfdb',
        connection_timeout=10
    )
    mc = maria_conn.cursor(dictionary=True)
    log.info('  MariaDB connecté ✅')
except Exception as e:
    log.error(f'  MariaDB connexion échouée: {e}')
    sys.exit(1)

# ── Colonnes supplémentaires ──────────────────────────────────────────────────
for col, defn in [
    ('mag_title',   'TEXT'),   # nom du magazine source
    ('mag_year',    'INTEGER'),# année du numéro
    ('mag_issn',    'TEXT'),   # ISSN du magazine
    ('ht_mag_code', 'TEXT'),   # rightsCode HathiTrust du numéro
]:
    try:
        sc.execute(f'ALTER TABLE works ADD COLUMN {col} {defn}')
    except Exception:
        pass
sqlite_conn.commit()

# ── Étape 1 : Récupérer les 215 cibles via MariaDB ───────────────────────────
log.info('\n=== ÉTAPE 1 : Croisement SQLite ↔ MariaDB ===')

# Récupérer les title_id SQLite qui ont dp_us=NULL et sont 1928-1963
sc.execute("""
    SELECT title_id, title, author, year
    FROM works
    WHERE year BETWEEN 1928 AND 1963
    AND dp_us IS NULL
    AND "type" IN ('shortfiction','novelette','novella','short story')
""")
sqlite_targets = {row['title_id']: dict(row) for row in sc.fetchall()}
log.info(f'  {len(sqlite_targets)} short fiction SQLite dp_us=NULL')

if not sqlite_targets:
    log.info('  Rien à traiter. Fin.')
    sys.exit(0)

# Dans MariaDB : retrouver les publications magazines pour ces title_id
# On cherche par titre + auteur + année
# Bulk query MariaDB — une seule requête, matching Python ensuite
log.info('  Bulk query MariaDB 1928-1963 magazines...')
mc.execute("""
    SELECT
        t.title_id   as isfdb_title_id,
        t.title_title,
        YEAR(t.title_copyright) as title_year,
        p.pub_title  as magazine,
        YEAR(p.pub_year) as pub_year,
        p.pub_id
    FROM titles t
    JOIN pub_content pc ON t.title_id = pc.title_id
    JOIN pubs p         ON pc.pub_id  = p.pub_id
    WHERE p.pub_ctype = 'MAGAZINE'
    AND YEAR(t.title_copyright) BETWEEN 1928 AND 1963
    AND t.title_ttype IN ('SHORTFICTION','NOVELETTE','NOVELLA')
    AND YEAR(p.pub_year) BETWEEN 1928 AND 1963
""")
maria_rows = mc.fetchall()
log.info(f'  {len(maria_rows)} publications magazines MariaDB récupérées')

# Index MariaDB par titre normalisé
import unicodedata
def norm(s):
    s = str(s).lower().strip()
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    return s[:40]

maria_index = {}
for row in maria_rows:
    key = (norm(row['title_title']), row['title_year'] or 0)
    maria_index.setdefault(key, []).append(row)

# Matching SQLite ↔ MariaDB
results = []
for tid, work in sqlite_targets.items():
    yr  = work['year'] or 0
    key = (norm(work['title']), yr)
    # Tolérance ±1 an
    for delta in (0, 1, -1):
        k = (norm(work['title']), yr + delta)
        if k in maria_index:
            for row in maria_index[k][:2]:
                results.append({
                    'sqlite_title_id': tid,
                    'sqlite_title':    work['title'],
                    'sqlite_year':     work['year'],
                    'magazine':        row['magazine'],
                    'pub_year':        row['pub_year'],
                    'pub_id':          row['pub_id'],
                })
            break

log.info(f'  {len(results)} correspondances trouvées dans MariaDB')

# Dédoublonner par magazine+année
mag_years = {}
for r in results:
    mag = r['magazine'] or ''
    yr  = r['pub_year'] or r['sqlite_year'] or 0
    key = (mag, yr)
    if key not in mag_years:
        mag_years[key] = []
    mag_years[key].append(r['sqlite_title_id'])

log.info(f'  {len(mag_years)} combinaisons magazine+année uniques')

# ── Étape 2 : HathiTrust par magazine+année ───────────────────────────────────
log.info('\n=== ÉTAPE 2 : HathiTrust par magazine+année ===')

ht_pd_total  = 0
ht_ic_total  = 0
ht_unk_total = 0
titles_dp    = []
titles_ic    = []

def base_mag(s):
    # "Amazing Stories, January 1940" -> "Amazing Stories"
    s = re.sub(r',\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec).*$', '', s, flags=re.IGNORECASE)
    s = re.sub(r',?\s*No\.?\s*\d+.*$', '', s, flags=re.IGNORECASE)
    s = re.sub(r',?\s*v\.?\s*\d+.*$', '', s, flags=re.IGNORECASE)
    return s.strip()

for (mag, yr), title_ids in sorted(mag_years.items()):
    if not mag or not yr:
        continue

    # Trouver l'ISSN
    issn = None
    mag_base = base_mag(mag)
    for known_mag, known_issn in MAGAZINE_ISSNS.items():
        if known_mag.lower() in mag_base.lower() or mag_base.lower() in known_mag.lower():
            issn = known_issn
            break

    result = None
    if issn:
        result = ht_check_issn(issn, yr)
        time.sleep(0.3)
    else:
        log.info(f'  ⚠️  Pas d\'ISSN pour "{mag}" — skip HathiTrust')

    status_icon = '✅' if result in ('pd', 'pd_probable') else '🔒' if result == 'ic' else '❓'
    log.info(f'  {status_icon} [{yr}] {mag[:50]:50s} → {result or "inconnu"} ({len(title_ids)} titres)')

    if result in ('pd', 'pd_probable'):
        ht_pd_total += len(title_ids)
        titles_dp.extend([(tid, mag, yr, issn, result) for tid in title_ids])
    elif result == 'ic':
        ht_ic_total += len(title_ids)
        titles_ic.extend([(tid, mag, yr, issn, result) for tid in title_ids])
    else:
        ht_unk_total += len(title_ids)

# ── Étape 3 : Mise à jour SQLite ─────────────────────────────────────────────
log.info('\n=== ÉTAPE 3 : Mise à jour SQLite ===')

for tid, mag, yr, issn, code in titles_dp:
    reason = (
        f'DP US — magazine "{mag}" ({yr}) non renouvelé (HathiTrust: {code}). '
        f'Le copyright du numéro n\'a pas été renouvelé → les nouvelles publiées '
        f'sont dans le domaine public. Source ISSN: {issn or "titre"}'
    )
    sc.execute("""
        UPDATE works SET
            dp_us=1,
            dp_us_reason=?,
            dp_us_source='hathitrust_magazine',
            mag_title=?,
            mag_year=?,
            mag_issn=?,
            ht_mag_code=?
        WHERE title_id=?
    """, (reason, mag, yr, issn, code, tid))

for tid, mag, yr, issn, code in titles_ic:
    reason = (
        f'Protégé — magazine "{mag}" ({yr}) renouvelé (HathiTrust: ic). '
        f'L\'éditeur a renouvelé le copyright de compilation.'
    )
    sc.execute("""
        UPDATE works SET
            dp_us=0,
            dp_us_reason=?,
            dp_us_source='hathitrust_magazine',
            mag_title=?,
            mag_year=?,
            mag_issn=?,
            ht_mag_code=?
        WHERE title_id=?
    """, (reason, mag, yr, issn, code, tid))

sqlite_conn.commit()

# ── Stats finales ─────────────────────────────────────────────────────────────
log.info('\n=== STATS FINALES ===')
log.info(f'  Titres → dp_us=1 (magazine DP)  : {ht_pd_total}')
log.info(f'  Titres → dp_us=0 (magazine ic)  : {ht_ic_total}')
log.info(f'  Titres → inconnu (pas d\'ISSN)   : {ht_unk_total}')

# Vérification DB
for label, sql in [
    ('dp_us=1 total',                 "SELECT COUNT(*) FROM works WHERE dp_us=1"),
    ('source hathitrust_magazine',    "SELECT COUNT(*) FROM works WHERE dp_us_source='hathitrust_magazine'"),
    ('DP sans VF short fiction',      "SELECT COUNT(*) FROM works WHERE dp_us=1 AND has_french_vf=0 AND \"type\" IN ('shortfiction','novelette','novella')"),
]:
    sc.execute(sql)
    log.info(f'  {label:45s}: {sc.fetchone()[0]}')

# Top nouvelles nouvellement DP
log.info('\n  Nouvelles nouvellement DP (magazines) :')
sc.execute("""
    SELECT title, author, year, mag_title, awards
    FROM works
    WHERE dp_us_source='hathitrust_magazine' AND dp_us=1
    ORDER BY award_count DESC, annualviews DESC
    LIMIT 20
""")
for row in sc.fetchall():
    log.info(f"  [{row[2]}] {row[1]} — {row[0]} (in {row[3]})")
    if row[4]:
        log.info(f"        {row[4][:80]}")

log.info(f'\n✅ Terminé à {datetime.now().strftime("%H:%M:%S")}')
sqlite_conn.close()
maria_conn.close()
