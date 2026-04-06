"""
21_translators.py v2
Récupère birth_year, death_year des traducteurs FR via Wikidata (+ noosfere fallback).
Calcule dp_year (death_year + 71) pour déterminer si traductions sont elles-mêmes DP.

Scope : Traducteurs prioritaires (VF ≤1995 OU œuvres primées DP)
Sources : Wikidata SPARQL → noosfere scraping (fallback)
"""
import fcntl, sys
_lf = open("/app/data/21.lock", "w")
try:
    fcntl.flock(_lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
except IOError:
    print("Instance deja en cours. Abandon."); sys.exit(0)

import sqlite3, requests, logging, time, re
from datetime import datetime
from bs4 import BeautifulSoup

DB       = '/app/data/sf_dp.sqlite'
LOG_FILE = '/app/data/21_translators.log'
WIKIDATA = 'https://query.wikidata.org/sparql'
NOOSFERE_SEARCH = 'https://www.noosfere.org/livres/niourf.asp'
HEADERS  = {
    'User-Agent': 'SF-Domaine-Public/1.0 (https://github.com/Maitresinh/sf-domaine-public; research project)',
    'Accept': 'application/sparql-results+json'
}
BATCH    = 50

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-7s %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()])
log = logging.getLogger()
log.info('=== 21_translators.py v2 ===')

conn = sqlite3.connect(DB, timeout=60)
conn.row_factory = sqlite3.Row
sc = conn.cursor()

# Table translators
sc.execute("""
    CREATE TABLE IF NOT EXISTS translators (
        name TEXT PRIMARY KEY,
        birth_year INTEGER,
        death_year INTEGER,
        nationality TEXT,
        wikidata_id TEXT,
        noosfere_id TEXT,
        dp_year INTEGER,
        searched INTEGER DEFAULT 0,
        source TEXT
    )
""")
conn.commit()
log.info('Table translators OK')

def normalize_name(name):
    """Normalise nom traducteur pour recherche."""
    if not name:
        return None
    # Supprimer parenthèses, points, "unknown translator"
    if 'unknown' in name.lower():
        return None
    name = re.sub(r'\([^)]*\)', '', name)
    name = re.sub(r'[.]', '', name)
    name = ' '.join(name.strip().split())
    return name if len(name) > 3 else None

def split_translators(raw):
    """Sépare traducteurs multiples."""
    if not raw:
        return []
    # Séparer sur &, /, , ou ;
    parts = re.split(r'[&/,;]', raw)
    result = []
    for p in parts:
        n = normalize_name(p)
        if n:
            result.append(n)
    return result

def query_wikidata(name):
    """Requête Wikidata SPARQL."""
    query = f"""
    SELECT DISTINCT ?person ?personLabel ?birth ?death ?nationalityLabel WHERE {{
      ?person rdfs:label "{name}"@fr .
      ?person wdt:P31 wd:Q5 .
      OPTIONAL {{ ?person wdt:P106 ?occupation }}
      OPTIONAL {{ ?person wdt:P569 ?birth }}
      OPTIONAL {{ ?person wdt:P570 ?death }}
      OPTIONAL {{ ?person wdt:P27 ?nationality }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "fr,en" }}
    }}
    LIMIT 5
    """
    try:
        r = requests.get(WIKIDATA, params={'query': query, 'format': 'json'}, 
                        headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None
        
        results = r.json().get('results', {}).get('bindings', [])
        
        # Chercher un traducteur en priorité
        for res in results:
            occ = res.get('occupationLabel', {}).get('value', '').lower()
            if 'traduct' in occ:
                birth = res.get('birth', {}).get('value', '')[:4]
                death = res.get('death', {}).get('value', '')[:4]
                nat = res.get('nationalityLabel', {}).get('value', '')
                wid = res.get('person', {}).get('value', '').split('/')[-1]
                return {
                    'birth_year': int(birth) if birth and birth.isdigit() else None,
                    'death_year': int(death) if death and death.isdigit() else None,
                    'nationality': nat[:50] if nat else None,
                    'wikidata_id': wid,
                    'source': 'wikidata'
                }
        
        # Sinon prendre le premier avec death_year
        for res in results:
            death = res.get('death', {}).get('value', '')[:4]
            if death and death.isdigit():
                birth = res.get('birth', {}).get('value', '')[:4]
                nat = res.get('nationalityLabel', {}).get('value', '')
                wid = res.get('person', {}).get('value', '').split('/')[-1]
                return {
                    'birth_year': int(birth) if birth and birth.isdigit() else None,
                    'death_year': int(death),
                    'nationality': nat[:50] if nat else None,
                    'wikidata_id': wid,
                    'source': 'wikidata'
                }
    except Exception as e:
        log.warning(f'Wikidata error {name}: {e}')
    return None

def scrape_noosfere(name):
    """Scrape noosfere pour birth/death (fallback)."""
    try:
        # Recherche par nom
        r = requests.get(NOOSFERE_SEARCH, params={'Mots': name}, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Chercher lien auteur
        for link in soup.find_all('a', href=True):
            if 'auteur.asp' in link['href'] and name.lower() in link.text.lower():
                author_url = 'https://www.noosfere.org/livres/' + link['href']
                
                # Fetch page auteur
                r2 = requests.get(author_url, headers=HEADERS, timeout=10)
                soup2 = BeautifulSoup(r2.text, 'html.parser')
                
                # Extraire dates (format : "Naissance : Ville, 1950")
                text = soup2.get_text()
                birth = re.search(r'Naissance\s*:.*?(\d{4})', text)
                death = re.search(r'Décès\s*:.*?(\d{4})', text)
                
                noosfere_id = re.search(r'NumAuteur=(\d+)', author_url)
                
                if death:
                    return {
                        'birth_year': int(birth.group(1)) if birth else None,
                        'death_year': int(death.group(1)),
                        'noosfere_id': noosfere_id.group(1) if noosfere_id else None,
                        'source': 'noosfere'
                    }
                break
    except Exception as e:
        log.warning(f'Noosfere error {name}: {e}')
    return None

# Extraire traducteurs prioritaires
log.info('Extraction traducteurs prioritaires...')
translators_raw = set()
for r in sc.execute("""
    SELECT DISTINCT last_vf_translator FROM works 
    WHERE last_vf_translator IS NOT NULL
    AND (
        (last_vf_year IS NOT NULL AND CAST(last_vf_year AS INTEGER) <= 1995)
        OR (dp_eu=1 AND dp_us=1 AND award_count > 0)
    )
""").fetchall():
    translators_raw.add(r['last_vf_translator'])

# Parser traducteurs multiples
translators = set()
for raw in translators_raw:
    for t in split_translators(raw):
        translators.add(t)

log.info(f'{len(translators)} traducteurs uniques ({len(translators_raw)} entrées brutes)')

# Filtrer déjà cherchés
existing = {r[0] for r in sc.execute("SELECT name FROM translators WHERE searched=1").fetchall()}
to_search = sorted(translators - existing)
log.info(f'{len(to_search)} à chercher ({len(existing)} déjà faits)')

n_done = n_wd = n_noos = n_notfound = 0

for name in to_search:
    # Wikidata d'abord
    data = query_wikidata(name)
    
    # Noosfere si pas trouvé
    if not data or not data.get('death_year'):
        noos_data = scrape_noosfere(name)
        if noos_data:
            data = noos_data
            n_noos += 1
        elif data:
            pass  # Gardé Wikidata sans death_year
    else:
        n_wd += 1
    
    if data and data.get('death_year'):
        dp_year = data['death_year'] + 71
        sc.execute("""
            INSERT OR REPLACE INTO translators 
            (name, birth_year, death_year, nationality, wikidata_id, noosfere_id, dp_year, searched, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
        """, (name, data.get('birth_year'), data['death_year'], 
              data.get('nationality'), data.get('wikidata_id'), 
              data.get('noosfere_id'), dp_year, data.get('source')))
        
        dp_status = '✅ DP' if dp_year <= 2026 else f'🔒 {dp_year}'
        src = data.get('source', '?')[:4]
        if n_done < 10 or (n_done+1) % 25 == 0:
            log.info(f'[{n_done+1:3d}] {name:30s} †{data["death_year"]} {dp_status} ({src})')
    else:
        sc.execute("INSERT OR IGNORE INTO translators (name, searched) VALUES (?, 1)", (name,))
        n_notfound += 1
    
    n_done += 1
    
    if n_done % BATCH == 0:
        conn.commit()
        log.info(f'CHECKPOINT {n_done}/{len(to_search)} — WD:{n_wd} Noos:{n_noos} NotFound:{n_notfound}')
    
    time.sleep(0.7)  # Rate limiting

conn.commit()

log.info('\n=== RESULTATS ===')
for label, sql in [
    ('Total translators', 'SELECT COUNT(*) FROM translators'),
    ('Avec death_year', 'SELECT COUNT(*) FROM translators WHERE death_year IS NOT NULL'),
    ('DP (dp_year <= 2026)', 'SELECT COUNT(*) FROM translators WHERE dp_year <= 2026'),
    ('Protégés encore', 'SELECT COUNT(*) FROM translators WHERE dp_year > 2026'),
    ('Non trouvés', 'SELECT COUNT(*) FROM translators WHERE death_year IS NULL AND searched=1'),
    ('Source Wikidata', 'SELECT COUNT(*) FROM translators WHERE source="wikidata"'),
    ('Source Noosfere', 'SELECT COUNT(*) FROM translators WHERE source="noosfere"'),
]:
    sc.execute(sql)
    log.info(f'  {label:30s}: {sc.fetchone()[0]:5d}')

log.info(f'\n✅ TERMINE {datetime.now().strftime("%H:%M:%S")}')
conn.close()
_lf.close()
