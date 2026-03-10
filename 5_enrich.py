import mysql.connector, sqlite_utils, requests, time
from collections import defaultdict

cn  = mysql.connector.connect(host='mariadb-sfdb', port=3306,
                               user='root', password='isfdb', database='isfdb')
cur = cn.cursor(dictionary=True)
db  = sqlite_utils.Database('/app/data/sf_dp.sqlite')

# Colonnes à ajouter si absentes
NEW_COLS = ['synopsis', 'rating', 'annualviews', 'nb_reviews', 'award_score',
            'wikipedia_url', 'goodreads_id', 'isfdb_tags', 'isfdb_lists',
            'translator', 'translator_dp', 'fantlab_rating', 'fantlab_votes',
            'ol_rating', 'ol_votes']
for col in NEW_COLS:
    try:
        db.execute('ALTER TABLE works ADD COLUMN ' + col + ' TEXT')
    except Exception:
        pass

# ── 1. Synopsis ───────────────────────────────────────────────────────────────
print('1. Synopsis...')
cur.execute("""
    SELECT t.title_id, n.note_note
    FROM titles t JOIN notes n ON t.title_synopsis = n.note_id
    WHERE t.title_synopsis IS NOT NULL
""")
synopsis_map = {r['title_id']: r['note_note'] for r in cur.fetchall()}
print('   ' + str(len(synopsis_map)) + ' synopsis')

# ── 2. Rating + annualviews ───────────────────────────────────────────────────
print('2. Rating/views...')
cur.execute("""
    SELECT title_id, title_rating, title_annualviews
    FROM titles WHERE title_rating IS NOT NULL OR title_annualviews > 0
""")
views_map = {r['title_id']: (r['title_rating'], r['title_annualviews'])
             for r in cur.fetchall()}
print('   ' + str(len(views_map)) + ' titres')

# ── 3. Awards via title_awards FK ────────────────────────────────────────────
print('3. Awards FK...')
cur.execute("""
    SELECT ta.title_id, at2.award_type_name, ac.award_cat_name, a.award_level
    FROM title_awards ta
    JOIN awards a        ON ta.award_id        = a.award_id
    JOIN award_cats ac   ON a.award_cat_id     = ac.award_cat_id
    JOIN award_types at2 ON ac.award_cat_type_id = at2.award_type_id
    WHERE a.award_level IN (1, 2)
""")
awards_map = defaultdict(list)
for r in cur.fetchall():
    awards_map[r['title_id']].append(r)
print('   ' + str(len(awards_map)) + ' titres avec awards')

# ── 4. award_titles_report score ─────────────────────────────────────────────
print('4. Award scores...')
cur.execute("SELECT title_id, score, year FROM award_titles_report")
score_map = {}
for r in cur.fetchall():
    tid = r['title_id']
    if tid not in score_map or r['score'] > score_map[tid][0]:
        score_map[tid] = (r['score'], r['year'])
print('   ' + str(len(score_map)) + ' titres avec score')

# ── 5. nb_reviews ─────────────────────────────────────────────────────────────
print('5. Reviews...')
cur.execute("SELECT title_id, reviews FROM most_reviewed")
reviews_map = {r['title_id']: r['reviews'] for r in cur.fetchall()}
print('   ' + str(len(reviews_map)) + ' titres')

# ── 6. Wikipedia URL ──────────────────────────────────────────────────────────
print('6. Wikipedia URLs...')
cur.execute("""
    SELECT title_id, url FROM webpages
    WHERE title_id IS NOT NULL AND url LIKE '%wikipedia%'
""")
wiki_map = {}
for r in cur.fetchall():
    if r['title_id'] not in wiki_map:
        wiki_map[r['title_id']] = r['url']
print('   ' + str(len(wiki_map)) + ' URLs')

# ── 7. Goodreads ID ───────────────────────────────────────────────────────────
print('7. Goodreads IDs...')
cur.execute("""
    SELECT pc.title_id, i.identifier_value
    FROM identifiers i
    JOIN identifier_types it ON i.identifier_type_id = it.identifier_type_id
    JOIN pub_content pc      ON i.pub_id = pc.pub_id
    WHERE it.identifier_type_name = 'Goodreads'
""")
goodreads_map = {}
for r in cur.fetchall():
    if r['title_id'] not in goodreads_map:
        goodreads_map[r['title_id']] = r['identifier_value']
print('   ' + str(len(goodreads_map)) + ' IDs')

# ── 8. Tags ISFDB ─────────────────────────────────────────────────────────────
print('8. Tags...')
NOISE = ['read by', 'read ', 'owned', 'wish list', 'audible', 'kindle',
         'award winner', 'award finalist', 'hugo award', 'nebula award',
         'locus award', 'campbell award', '1-award']
LISTS = ['masterwork', 'core collection', 'best novels', 'best sf',
         'best science fiction', '100 best', '50 essential', 'anatomy of wonder',
         'reading list', 'recommended']

def is_noise(tag):
    t = tag.lower()
    return any(n in t for n in NOISE)
def is_list(tag):
    t = tag.lower()
    return any(l in t for l in LISTS)

cur.execute("""
    SELECT tm.title_id, t.tag_name FROM tag_mapping tm
    JOIN tags t ON tm.tag_id = t.tag_id WHERE t.tag_status = 0
""")
tags_map  = defaultdict(list)
lists_map = defaultdict(list)
for r in cur.fetchall():
    tag = r['tag_name'].strip()
    tid = r['title_id']
    if is_noise(tag): continue
    if is_list(tag):  lists_map[tid].append(tag)
    else:             tags_map[tid].append(tag)
print('   ' + str(len(tags_map)) + ' titres avec tags')

# ── 9. Traducteurs depuis title_translator ────────────────────────────────────
# Format : "langue,année,Nom Prénom;langue,année,Nom Prénom"
print('9. Traducteurs...')
cur.execute("""
    SELECT title_id, title_translator FROM titles
    WHERE title_translator IS NOT NULL AND title_translator != ''
""")
translator_map = {}
for r in cur.fetchall():
    raw = r['title_translator'].strip()
    if not raw:
        continue
    parts = []
    for chunk in raw.split(';'):
        chunk = chunk.strip()
        fields = chunk.split(',')
        if len(fields) >= 3:
            lang, year, name = fields[0].strip(), fields[1].strip(), ','.join(fields[2:]).strip()
            parts.append(name + ' (' + lang + ' ' + year + ')')
        elif len(fields) == 1 and chunk:
            parts.append(chunk)
    if parts:
        translator_map[r['title_id']] = '; '.join(parts)
print('   ' + str(len(translator_map)) + ' titres avec traducteur')

# ── 10. DP traducteur via trans_authors → authors ────────────────────────────
# trans_authors.author_id → authors.author_deathdate
print('10. DP traducteurs...')
cur.execute("""
    SELECT ta.trans_author_name, a.author_deathdate
    FROM trans_authors ta
    LEFT JOIN authors a ON ta.author_id = a.author_id
    WHERE a.author_deathdate IS NOT NULL
""")
# On stocke les noms de traducteurs connus décédés avant 1956 (DP EU)
translator_dp_set = set()
for r in cur.fetchall():
    dd = r['author_deathdate']
    if dd and dd.year < 1956:
        translator_dp_set.add(r['trans_author_name'].lower().strip())
print('   ' + str(len(translator_dp_set)) + ' traducteurs DP EU connus')

def get_translator_dp(translator_str):
    if not translator_str:
        return None
    names = [p.split('(')[0].strip().lower() for p in translator_str.split(';')]
    if all(n in translator_dp_set for n in names if n):
        return 'dp_eu'
    return 'inconnu'

# ── 11. FantLab ratings ───────────────────────────────────────────────────────
print('11. FantLab ratings (romans DP EU sans VF uniquement)...')
novels_dp = list(db.execute("""
    SELECT title_id, title, author FROM works
    WHERE type='novel' AND dp_eu=1 AND has_french_vf=0
""").fetchall())
print('   ' + str(len(novels_dp)) + ' romans a interroger')

fantlab_map = {}
for i, (tid, title, author) in enumerate(novels_dp):
    if i % 100 == 0:
        print('   FantLab ' + str(i) + '/' + str(len(novels_dp)))
    try:
        q = title + ' ' + (author or '')
        r = requests.get('https://fantlab.ru/api/search-main',
                         params={'q': q, 'page': 1}, timeout=8)
        data = r.json()
        works_list = data.get('works', [])
        if works_list:
            w = works_list[0]
            fantlab_map[tid] = (
                str(w.get('rating', {}).get('rating', '')),
                str(w.get('rating', {}).get('voters', ''))
            )
    except Exception:
        pass
    time.sleep(0.3)
print('   FantLab : ' + str(len(fantlab_map)) + ' trouvés')

# ── 12. Open Library ratings ─────────────────────────────────────────────────
print('12. Open Library ratings...')
ol_map = {}
for i, (tid, title, author) in enumerate(novels_dp):
    if i % 100 == 0:
        print('   OL ' + str(i) + '/' + str(len(novels_dp)))
    try:
        r = requests.get('https://openlibrary.org/search.json',
                         params={'title': title, 'author': author or '', 'limit': 1},
                         timeout=8)
        docs = r.json().get('docs', [])
        if docs:
            d = docs[0]
            rating  = d.get('ratings_average')
            votes   = d.get('ratings_count')
            if rating:
                ol_map[tid] = (str(round(rating, 2)), str(votes or 0))
    except Exception:
        pass
    time.sleep(0.2)
print('   OL : ' + str(len(ol_map)) + ' trouvés')

# ── 13. Assemblage et écriture ────────────────────────────────────────────────
works = list(db.execute('SELECT title_id FROM works').fetchall())
print('\n13. Assemblage ' + str(len(works)) + ' oeuvres...')

updates = []
for (title_id,) in works:
    aw = awards_map.get(title_id, [])
    parts = [('🏆' if a['award_level'] == '1' else '🏅') +
             a['award_type_name'] + ' – ' + a['award_cat_name'] for a in aw]

    rv      = views_map.get(title_id, (None, None))
    sc      = score_map.get(title_id, (None, None))
    fl      = fantlab_map.get(title_id, (None, None))
    ol      = ol_map.get(title_id, (None, None))
    trans   = translator_map.get(title_id)

    updates.append({
        'title_id':       title_id,
        'synopsis':       synopsis_map.get(title_id),
        'rating':         str(rv[0]) if rv[0] else None,
        'annualviews':    rv[1],
        'nb_reviews':     reviews_map.get(title_id),
        'award_score':    sc[0],
        'awards':         ' | '.join(parts) if parts else None,
        'award_count':    len(aw),
        'wikipedia_url':  wiki_map.get(title_id),
        'goodreads_id':   goodreads_map.get(title_id),
        'isfdb_tags':     ', '.join(tags_map.get(title_id, []))  or None,
        'isfdb_lists':    ', '.join(lists_map.get(title_id, [])) or None,
        'translator':     trans,
        'translator_dp':  get_translator_dp(trans),
        'fantlab_rating': fl[0],
        'fantlab_votes':  fl[1],
        'ol_rating':      ol[0],
        'ol_votes':       ol[1],
    })

print('Ecriture...')
db['works'].upsert_all(updates, pk='title_id')
print('OK')

# ── 14. Stats finales ─────────────────────────────────────────────────────────
print('\n=== Stats enrichissement ===')
for label, sql in [
    ('Avec synopsis',     'SELECT COUNT(*) FROM works WHERE synopsis IS NOT NULL'),
    ('Avec awards FK',    'SELECT COUNT(*) FROM works WHERE award_count > 0'),
    ('Avec award_score',  'SELECT COUNT(*) FROM works WHERE award_score IS NOT NULL'),
    ('Avec Wikipedia',    'SELECT COUNT(*) FROM works WHERE wikipedia_url IS NOT NULL'),
    ('Avec Goodreads',    'SELECT COUNT(*) FROM works WHERE goodreads_id IS NOT NULL'),
    ('Avec tags',         'SELECT COUNT(*) FROM works WHERE isfdb_tags IS NOT NULL'),
    ('Avec traducteur',   'SELECT COUNT(*) FROM works WHERE translator IS NOT NULL'),
    ('Avec FantLab',      'SELECT COUNT(*) FROM works WHERE fantlab_rating IS NOT NULL'),
    ('Avec OL rating',    'SELECT COUNT(*) FROM works WHERE ol_rating IS NOT NULL'),
]:
    print(label + ': ' + str(db.execute(sql).fetchone()[0]))

print('\n=== Top 10 romans DP EU sans VF ===')
for r in db.execute("""
    SELECT title, author, year, rating, annualviews, award_count,
           award_score, nb_reviews, fantlab_rating, ol_rating,
           isfdb_tags, synopsis
    FROM works
    WHERE type='novel' AND dp_eu=1 AND has_french_vf=0
    ORDER BY annualviews DESC
    LIMIT 10
""").fetchall():
    print(r)

cn.close()
