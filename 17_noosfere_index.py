"""
17_noosfere_index.py
Scrape l'index des critiques noosfere.org (toutes les lettres)
et construit la table noosfere_critiques dans sf_dp.sqlite.

Table créée :
  noosfere_critiques(
    numlivre       INTEGER PRIMARY KEY,
    titre_noosfere TEXT,
    auteur_noosfere TEXT,
    lettre         TEXT,
    critique_fetched INTEGER DEFAULT 0  -- flag pour 18_
  )

Usage : docker exec sf-dp-tools python3 /app/17_noosfere_index.py
"""

import sqlite3, requests, time, logging
from bs4 import BeautifulSoup

# ── Config ────────────────────────────────────────────────────────────────────
DB      = "/app/data/sf_dp.sqlite"
BASE    = "https://www.noosfere.org/livres/critiques.asp"
DELAY   = 1.5   # secondes entre requêtes (poli)
LETTERS = ["0"] + [chr(c) for c in range(ord("A"), ord("Z") + 1)]

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

# ── DB ────────────────────────────────────────────────────────────────────────
def init_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS noosfere_critiques (
            numlivre        INTEGER PRIMARY KEY,
            titre_noosfere  TEXT,
            auteur_noosfere TEXT,
            lettre          TEXT,
            critique_fetched INTEGER DEFAULT 0
        )
    """)
    conn.commit()

def insert_entry(conn, numlivre, titre, auteur, lettre):
    conn.execute("""
        INSERT OR IGNORE INTO noosfere_critiques
            (numlivre, titre_noosfere, auteur_noosfere, lettre)
        VALUES (?, ?, ?, ?)
    """, (numlivre, titre, auteur, lettre))

# ── Scraping ──────────────────────────────────────────────────────────────────
def fetch_letter(lettre):
    """Retourne liste de (numlivre, titre, auteur) pour une lettre."""
    url = BASE
    params = {"lettre": lettre}
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        r.raise_for_status()
    except Exception as e:
        log.error(f"  [{lettre}] erreur HTTP : {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    results = []

    # Les liens alternent : niourf (livre) puis auteur.asp
    # On parcourt tous les <a> et on apparie les paires
    links = soup.find_all("a", href=True)
    i = 0
    while i < len(links):
        a = links[i]
        href = a["href"]

        if "niourf.asp" in href and "numlivre=" in href:
            titre = a.get_text(strip=True)
            # Extraire numlivre
            try:
                numlivre = int(href.split("numlivre=")[1].split("&")[0])
            except ValueError:
                i += 1
                continue

            # Chercher l'auteur dans le lien suivant
            auteur = ""
            if i + 1 < len(links):
                next_a = links[i + 1]
                if "auteur.asp" in next_a["href"]:
                    auteur = next_a.get_text(strip=True)
                    i += 1  # consommer aussi le lien auteur

            results.append((numlivre, titre, auteur))

        i += 1

    return results

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    conn = sqlite3.connect(DB)
    init_db(conn)

    # Compter l'existant
    existing = conn.execute("SELECT COUNT(*) FROM noosfere_critiques").fetchone()[0]
    log.info(f"Table noosfere_critiques : {existing} entrées existantes")

    total_new = 0

    for lettre in LETTERS:
        entries = fetch_letter(lettre)
        new = 0
        for numlivre, titre, auteur in entries:
            insert_entry(conn, numlivre, titre, auteur, lettre)
            new += 1
        conn.commit()
        total_new += new
        log.info(f"  Lettre {lettre:>2} : {len(entries):4d} livres trouvés  (+{new} nouveaux)")
        time.sleep(DELAY)

    final = conn.execute("SELECT COUNT(*) FROM noosfere_critiques").fetchone()[0]
    log.info(f"✅ DONE — {total_new} insérés, total table : {final}")
    conn.close()

if __name__ == "__main__":
    main()
