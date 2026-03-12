"""
18_noosfere_critiques.py
Pour chaque entrée de noosfere_critiques (indexée par 17_),
fetche niourf.asp?numlivre=X et extrait les critiques.

Tables créées/modifiées :
  noosfere_textes(id, numlivre, chroniqueur, texte, is_serie)
  noosfere_critiques : ajoute title_id (matching works), nb_critiques

Usage : docker exec sf-dp-tools python3 /app/18_noosfere_critiques.py
"""

import sqlite3, requests, time, logging, unicodedata, re

DB    = "/app/data/sf_dp.sqlite"
BASE  = "https://www.noosfere.org/livres/niourf.asp"
DELAY = 1.2
BATCH = 50   # commit tous les N livres

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

# ── Normalisation pour matching ───────────────────────────────────────────────
def normalize(s):
    """Lowercase, sans accents, sans ponctuation — pour fuzzy match."""
    if not s:
        return ""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

# ── DB ────────────────────────────────────────────────────────────────────────
def migrate(conn):
    cols = {r[1] for r in conn.execute("PRAGMA table_info(noosfere_critiques)")}
    if "title_id" not in cols:
        conn.execute("ALTER TABLE noosfere_critiques ADD COLUMN title_id INTEGER")
    if "nb_critiques" not in cols:
        conn.execute("ALTER TABLE noosfere_critiques ADD COLUMN nb_critiques INTEGER DEFAULT 0")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS noosfere_textes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            numlivre    INTEGER NOT NULL,
            chroniqueur TEXT,
            texte       TEXT,
            is_serie    INTEGER DEFAULT 0,
            FOREIGN KEY (numlivre) REFERENCES noosfere_critiques(numlivre)
        )
    """)
    conn.commit()

def build_works_index(conn):
    """Index titre EN + titre FR -> title_id pour le matching noosfere."""
    idx = {}
    for title_id, title, french_title, author in conn.execute(
        "SELECT title_id, title, french_title, author FROM works"
    ):
        a = normalize(author)
        if title:
            idx[(normalize(title), a)] = title_id
        if french_title:
            idx[(normalize(french_title), a)] = title_id
    log.info(f"Index works : {len(idx)} entrees (EN + FR)")
    return idx

def match_work(idx, titre_noo, auteur_noo):
    """Tente un match exact normalisé, puis titre seul."""
    key = (normalize(titre_noo), normalize(auteur_noo))
    if key in idx:
        return idx[key]
    # Fallback : titre seul (premier match)
    t = normalize(titre_noo)
    for (kt, _), tid in idx.items():
        if kt == t:
            return tid
    return None

# ── Parsing HTML ──────────────────────────────────────────────────────────────
def parse_critiques(html):
    """Retourne liste de dict {chroniqueur, texte, is_serie}."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    results = []

    for div in soup.find_all("div", id="critique"):
        # Détecter critique de série
        is_serie = any(
            "serie.asp" in a.get("href", "")
            for a in div.find_all("a", href=True)
        )

        # Chroniqueur
        chroniqueur = None
        for a in div.find_all("a", href=True):
            if "critsign.asp" in a["href"]:
                chroniqueur = a.get_text(strip=True)
                break

        # Texte : concat des div align=justify
        paragraphes = [
            p.get_text(" ", strip=True)
            for p in div.find_all("div", align="justify")
            if p.get_text(strip=True)
        ]
        texte = "\n\n".join(paragraphes) if paragraphes else None

        # Ne garder que si texte ou chroniqueur présent
        if texte or chroniqueur:
            results.append({
                "chroniqueur": chroniqueur,
                "texte": texte,
                "is_serie": int(is_serie),
            })

    return results

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    conn = sqlite3.connect(DB)
    migrate(conn)

    # Index works pour matching
    works_idx = build_works_index(conn)

    # Entrées à traiter
    todo = conn.execute("""
        SELECT numlivre, titre_noosfere, auteur_noosfere
        FROM noosfere_critiques
        WHERE critique_fetched = 0
        ORDER BY numlivre
    """).fetchall()
    log.info(f"{len(todo)} livres à traiter")

    ok = err = matched = 0

    for i, (numlivre, titre, auteur) in enumerate(todo):
        try:
            r = requests.get(
                BASE, params={"numlivre": numlivre},
                headers=HEADERS, timeout=15
            )
            r.raise_for_status()
            r.encoding = "iso-8859-1"  # noosfere est en latin-1
        except Exception as e:
            log.warning(f"  [{numlivre}] erreur HTTP : {e}")
            err += 1
            time.sleep(DELAY)
            continue

        critiques = parse_critiques(r.text)
        nb = len(critiques)

        # Matching ISFDB
        title_id = match_work(works_idx, titre, auteur)
        if title_id:
            matched += 1

        # Insérer les textes
        for c in critiques:
            conn.execute("""
                INSERT INTO noosfere_textes (numlivre, chroniqueur, texte, is_serie)
                VALUES (?, ?, ?, ?)
            """, (numlivre, c["chroniqueur"], c["texte"], c["is_serie"]))

        # Marquer comme traité
        conn.execute("""
            UPDATE noosfere_critiques
            SET critique_fetched = 1,
                title_id         = ?,
                nb_critiques     = ?
            WHERE numlivre = ?
        """, (title_id, nb, numlivre))

        ok += 1
        if nb:
            log.info(f"  [{numlivre}] {titre[:40]:<40} → {nb} critique(s)"
                     f"  {'✅ match' if title_id else '❌ no match'}")

        if i % BATCH == 0 and i > 0:
            conn.commit()
            log.info(f"  --- commit {i}/{len(todo)} ---")

        time.sleep(DELAY)

    conn.commit()

    # Stats finales
    total_textes = conn.execute("SELECT COUNT(*) FROM noosfere_textes").fetchone()[0]
    log.info(f"\n✅ DONE")
    log.info(f"   Traités : {ok}  Erreurs : {err}")
    log.info(f"   Matchés avec works : {matched}/{ok}")
    log.info(f"   Textes stockés : {total_textes}")
    conn.close()

if __name__ == "__main__":
    main()
