"""
19_noosfere_rematch.py
Rematch des noosfere_critiques où title_id IS NULL.
Stratégie : refetche niourf.asp, extrait "Titre original : X, année"
puis matche sur normalize(X) dans works.title.

Usage : docker exec sf-dp-tools python3 /app/19_noosfere_rematch.py
"""

import sqlite3, requests, time, logging, unicodedata, re

DB    = "/app/data/sf_dp.sqlite"
BASE  = "https://www.noosfere.org/livres/niourf.asp"
DELAY = 1.0
BATCH = 100

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64; rv:123.0) "
        "Gecko/20100101 Firefox/123.0"
    )
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

RE_TITRE_ORIG = re.compile(r'Titre original\s*:\s*(.+?),\s*\d{4}')

def normalize(s):
    if not s:
        return ""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower()
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def build_title_index(conn):
    """Index normalize(title) → title_id (titres EN/originaux uniquement)."""
    idx = {}
    for title_id, title in conn.execute("SELECT title_id, title FROM works WHERE title IS NOT NULL"):
        k = normalize(title)
        if k:
            idx[k] = title_id
    log.info(f"Index titres : {len(idx)} entrées")
    return idx

def fetch_titre_original(numlivre):
    """Fetche la fiche noosfere et extrait le titre original anglais."""
    try:
        r = requests.get(BASE, params={"numlivre": numlivre},
                         headers=HEADERS, timeout=15)
        r.raise_for_status()
        r.encoding = "iso-8859-1"
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, "html.parser")
        fiche = soup.find("div", id="Fiche_livre")
        if not fiche:
            return None
        texte = fiche.get_text(" ", strip=True)
        m = RE_TITRE_ORIG.search(texte)
        return m.group(1).strip() if m else None
    except Exception as e:
        log.warning(f"  [{numlivre}] erreur : {e}")
        return None

def main():
    conn = sqlite3.connect(DB)

    # Entrées sans match
    todo = conn.execute("""
        SELECT numlivre, titre_noosfere, auteur_noosfere
        FROM noosfere_critiques
        WHERE critique_fetched = 1 AND title_id IS NULL
        ORDER BY numlivre
    """).fetchall()
    log.info(f"{len(todo)} entrées sans title_id à rematcher")

    idx = build_title_index(conn)

    matched = skipped = err = 0

    for i, (numlivre, titre, auteur) in enumerate(todo):
        titre_orig = fetch_titre_original(numlivre)

        if not titre_orig:
            # Pas de titre original → œuvre francophone native (pas dans works EN)
            skipped += 1
            time.sleep(DELAY)
            continue

        title_id = idx.get(normalize(titre_orig))

        if title_id:
            conn.execute(
                "UPDATE noosfere_critiques SET title_id=? WHERE numlivre=?",
                (title_id, numlivre)
            )
            matched += 1
            log.info(f"  ✅ [{numlivre}] {titre_orig[:45]:<45} → title_id={title_id}")
        else:
            # Titre original trouvé mais pas dans works (hors périmètre DP, ou type filtré)
            skipped += 1
            log.debug(f"  ❌ [{numlivre}] '{titre_orig}' non trouvé dans works")

        if i % BATCH == 0 and i > 0:
            conn.commit()
            log.info(f"  --- commit {i}/{len(todo)} | matchés={matched} ---")

        time.sleep(DELAY)

    conn.commit()
    log.info(f"\n✅ DONE — matchés={matched}, sans titre orig={skipped}, erreurs={err}")
    log.info(f"   Total matchés dans noosfere_critiques : "
             f"{conn.execute('SELECT COUNT(*) FROM noosfere_critiques WHERE title_id IS NOT NULL').fetchone()[0]}")
    conn.close()

if __name__ == "__main__":
    main()
